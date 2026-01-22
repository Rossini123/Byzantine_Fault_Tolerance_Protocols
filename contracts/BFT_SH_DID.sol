// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title BFT_SH_DID - Byzantine Fault Tolerant Self-Healing DID Registry
 * @notice Implements recovery protocol with 2f+1 watcher quorum
 * @dev Based on the formal model in the paper
 */
contract BFT_SH_DID {
    
    struct DIDRecord {
        address controller;
        bytes32 docCID;          // IPFS content identifier
        uint256 version;
        uint256 lastModified;
        bool active;
    }
    
    struct WatcherSet {
        address[] watchers;
        uint256 threshold;       // 2f+1
        uint256 epoch;
        mapping(address => bool) isWatcher;
    }
    
    struct RecoveryProposal {
        bytes32 did;
        bytes32 newDocCID;
        address newController;
        uint256 nonce;
        uint256 epoch;
        bytes32 proposalHash;
    }
    
    // State
    mapping(bytes32 => DIDRecord) public dids;
    mapping(bytes32 => WatcherSet) private watcherSets;
    mapping(bytes32 => mapping(uint256 => bool)) public recoveryCompleted; // did => epoch => completed
    
    // Events
    event DIDCreated(bytes32 indexed did, address controller, bytes32 docCID);
    event DIDUpdated(bytes32 indexed did, bytes32 newDocCID, uint256 version);
    event RecoveryInitiated(bytes32 indexed did, uint256 epoch, bytes32 proposalHash);
    event RecoveryCommitted(bytes32 indexed did, address newController, uint256 epoch);
    event WatcherSetUpdated(bytes32 indexed did, uint256 epoch, uint256 threshold);
    
    // Errors
    error UnauthorizedController();
    error DIDNotActive();
    error InvalidSignatureCount();
    error RecoveryAlreadyCompleted();
    error InvalidWatcherSignature();
    error ThresholdNotMet();
    error EpochMismatch();
    
    /**
     * @notice Create a new DID
     */
    function createDID(
        bytes32 did,
        address controller,
        bytes32 docCID
    ) external {
        require(dids[did].controller == address(0), "DID already exists");
        
        dids[did] = DIDRecord({
            controller: controller,
            docCID: docCID,
            version: 0,
            lastModified: block.timestamp,
            active: true
        });
        
        emit DIDCreated(did, controller, docCID);
    }
    
    /**
     * @notice Setup watcher set for a DID
     * @param did The DID identifier
     * @param watchers Array of watcher addresses
     * @param f Byzantine fault tolerance parameter (threshold = 2f+1)
     */
    function setupWatchers(
        bytes32 did,
        address[] calldata watchers,
        uint256 f
    ) external {
        require(dids[did].controller == msg.sender, "Not controller");
        require(watchers.length >= 3 * f + 1, "Insufficient watchers for f");
        
        WatcherSet storage ws = watcherSets[did];
        ws.epoch++;
        ws.threshold = 2 * f + 1;
        
        // Clear old watchers
        for (uint i = 0; i < ws.watchers.length; i++) {
            ws.isWatcher[ws.watchers[i]] = false;
        }
        delete ws.watchers;
        
        // Set new watchers
        for (uint i = 0; i < watchers.length; i++) {
            ws.watchers.push(watchers[i]);
            ws.isWatcher[watchers[i]] = true;
        }
        
        emit WatcherSetUpdated(did, ws.epoch, ws.threshold);
    }
    
    /**
     * @notice COMMIT_RECOVERY - Core recovery function with BFT guarantees
     * @param did The DID being recovered
     * @param newDocCID New DID Document CID
     * @param newController New controller address
     * @param nonce Unique nonce for replay prevention
     * @param epoch Recovery epoch
     * @param signatures Array of watcher signatures (2f+1 required)
     */
    function commitRecovery(
        bytes32 did,
        bytes32 newDocCID,
        address newController,
        uint256 nonce,
        uint256 epoch,
        bytes[] calldata signatures
    ) external {
        DIDRecord storage record = dids[did];
        if (!record.active) revert DIDNotActive();
        
        WatcherSet storage ws = watcherSets[did];
        if (epoch != ws.epoch) revert EpochMismatch();
        if (recoveryCompleted[did][epoch]) revert RecoveryAlreadyCompleted();
        if (signatures.length < ws.threshold) revert ThresholdNotMet();
        
        // Construct proposal hash (EIP-712 style)
        bytes32 proposalHash = keccak256(abi.encodePacked(
            did,
            newDocCID,
            newController,
            nonce,
            epoch,
            address(this),
            block.chainid
        ));
        
        // Verify signatures
        uint256 validSignatures = 0;
        address[] memory signers = new address[](signatures.length);
        
        for (uint i = 0; i < signatures.length; i++) {
            address signer = recoverSigner(proposalHash, signatures[i]);
            
            // Check if signer is a watcher and hasn't signed twice
            if (ws.isWatcher[signer]) {
                bool duplicate = false;
                for (uint j = 0; j < validSignatures; j++) {
                    if (signers[j] == signer) {
                        duplicate = true;
                        break;
                    }
                }
                if (!duplicate) {
                    signers[validSignatures] = signer;
                    validSignatures++;
                }
            }
        }
        
        if (validSignatures < ws.threshold) revert InvalidSignatureCount();
        
        // Commit recovery
        record.controller = newController;
        record.docCID = newDocCID;
        record.version++;
        record.lastModified = block.timestamp;
        recoveryCompleted[did][epoch] = true;
        
        emit RecoveryCommitted(did, newController, epoch);
    }
    
    /**
     * @notice Recover signer from signature
     */
    function recoverSigner(
        bytes32 messageHash,
        bytes memory signature
    ) internal pure returns (address) {
        require(signature.length == 65, "Invalid signature length");
        
        bytes32 r;
        bytes32 s;
        uint8 v;
        
        assembly {
            r := mload(add(signature, 32))
            s := mload(add(signature, 64))
            v := byte(0, mload(add(signature, 96)))
        }
        
        if (v < 27) v += 27;
        require(v == 27 || v == 28, "Invalid signature v");
        
        bytes32 ethSignedHash = keccak256(abi.encodePacked(
            "\x19Ethereum Signed Message:\n32",
            messageHash
        ));
        
        return ecrecover(ethSignedHash, v, r, s);
    }
    
    /**
     * @notice Get watcher set info
     */
    function getWatcherInfo(bytes32 did) external view returns (
        address[] memory watchers,
        uint256 threshold,
        uint256 epoch
    ) {
        WatcherSet storage ws = watcherSets[did];
        return (ws.watchers, ws.threshold, ws.epoch);
    }
    
    /**
     * @notice Resolve DID
     */
    function resolveDID(bytes32 did) external view returns (
        address controller,
        bytes32 docCID,
        uint256 version,
        uint256 lastModified,
        bool active
    ) {
        DIDRecord memory record = dids[did];
        return (
            record.controller,
            record.docCID,
            record.version,
            record.lastModified,
            record.active
        );
    }
}
