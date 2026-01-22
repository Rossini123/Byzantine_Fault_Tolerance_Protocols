"""
BFT-MV-DID: Byzantine Fault Tolerant Multi-View DID Reconciliation
Simulation framework for experimental evaluation
"""

import random
import time
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional
from enum import Enum
import hashlib


class AgentType(Enum):
    HONEST = "honest"
    BYZANTINE = "byzantine"


@dataclass
class DIDView:
    """Local view of a DID at an agent"""
    did: str
    version: int
    doc_hash: str
    timestamp: float
    
    def __hash__(self):
        return hash((self.did, self.version, self.doc_hash))
    
    def __eq__(self, other):
        if not isinstance(other, DIDView):
            return False
        return (self.did == other.did and 
                self.version == other.version and 
                self.doc_hash == other.doc_hash)


@dataclass
class Agent:
    """Agent in the multi-view reconciliation protocol"""
    agent_id: int
    agent_type: AgentType
    local_view: Optional[DIDView] = None
    peers: List[int] = field(default_factory=list)
    messages_sent: int = 0
    messages_received: int = 0
    ledger_queries: int = 0
    
    def is_byzantine(self) -> bool:
        return self.agent_type == AgentType.BYZANTINE


@dataclass
class Message:
    """Protocol message"""
    sender: int
    receiver: int
    msg_type: str  # "SUMMARY", "REQDIFF", "DIFF"
    view: Optional[DIDView] = None
    operations: List[Dict] = field(default_factory=list)
    round_num: int = 0


class BFTMVDIDNetwork:
    """
    Simulates BFT-MV-DID protocol with configurable parameters
    """
    
    def __init__(
        self,
        n_agents: int,
        f_byzantine: int,
        fanout: int,
        did: str = "did:example:123"
    ):
        """
        Initialize network
        
        Args:
            n_agents: Total number of agents
            f_byzantine: Number of Byzantine agents
            fanout: Number of peers each agent contacts per round
            did: The DID being reconciled
        """
        self.n_agents = n_agents
        self.f_byzantine = f_byzantine
        self.fanout = min(fanout, n_agents - 1)
        self.did = did
        
        # Initialize agents
        self.agents: List[Agent] = []
        byzantine_ids = set(random.sample(range(n_agents), f_byzantine))
        
        for i in range(n_agents):
            agent_type = AgentType.BYZANTINE if i in byzantine_ids else AgentType.HONEST
            self.agents.append(Agent(agent_id=i, agent_type=agent_type))
        
        # Ground truth (ledger state)
        self.ledger_view = DIDView(
            did=did,
            version=10,
            doc_hash=self._compute_hash("ledger_doc_v10"),
            timestamp=time.time()
        )
        
        # Initialize divergent views
        self._initialize_views()
        
        # Statistics
        self.round_num = 0
        self.total_messages = 0
        self.total_ledger_queries = 0
        self.convergence_round: Optional[int] = None
    
    def _compute_hash(self, data: str) -> str:
        """Compute hash of data"""
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _initialize_views(self):
        """Initialize agents with stale/divergent views"""
        for agent in self.agents:
            if agent.is_byzantine():
                # Byzantine agents report false views
                agent.local_view = DIDView(
                    did=self.did,
                    version=random.randint(5, 15),  # Random false version
                    doc_hash=self._compute_hash(f"fake_doc_{agent.agent_id}"),
                    timestamp=time.time()
                )
            else:
                # Honest agents start with stale views
                stale_version = random.randint(5, 9)
                agent.local_view = DIDView(
                    did=self.did,
                    version=stale_version,
                    doc_hash=self._compute_hash(f"ledger_doc_v{stale_version}"),
                    timestamp=time.time() - random.uniform(10, 100)
                )
    
    def _select_peers(self, agent_id: int) -> List[int]:
        """Select random peers for an agent (fanout)"""
        all_others = [i for i in range(self.n_agents) if i != agent_id]
        return random.sample(all_others, min(self.fanout, len(all_others)))
    
    def _honest_agent_summary(self, agent: Agent) -> Message:
        """Honest agent sends SUMMARY of local view"""
        return Message(
            sender=agent.agent_id,
            receiver=-1,  # Broadcast
            msg_type="SUMMARY",
            view=agent.local_view,
            round_num=self.round_num
        )
    
    def _byzantine_agent_summary(self, agent: Agent) -> Message:
        """Byzantine agent may lie about version"""
        fake_view = DIDView(
            did=self.did,
            version=random.randint(8, 20),  # Lie about version
            doc_hash=self._compute_hash(f"byzantine_{random.randint(0, 100)}"),
            timestamp=time.time()
        )
        return Message(
            sender=agent.agent_id,
            receiver=-1,
            msg_type="SUMMARY",
            view=fake_view,
            round_num=self.round_num
        )
    
    def _handle_summary(self, receiver: Agent, summary: Message):
        """Agent handles received SUMMARY"""
        receiver.messages_received += 1
        
        if receiver.is_byzantine():
            return  # Byzantine agents don't update
        
        sender_view = summary.view
        
        # Compare versions
        if sender_view.version > receiver.local_view.version:
            # Version ahead - might be false, query ledger
            receiver.ledger_queries += 1
            self.total_ledger_queries += 1
            
            # Honest agents get ground truth from ledger
            receiver.local_view = DIDView(
                did=self.ledger_view.did,
                version=self.ledger_view.version,
                doc_hash=self.ledger_view.doc_hash,
                timestamp=time.time()
            )
        
        elif sender_view.version == receiver.local_view.version:
            if sender_view.doc_hash != receiver.local_view.doc_hash:
                # Same version, different hash - conflict! Query ledger
                receiver.ledger_queries += 1
                self.total_ledger_queries += 1
                receiver.local_view = DIDView(
                    did=self.ledger_view.did,
                    version=self.ledger_view.version,
                    doc_hash=self.ledger_view.doc_hash,
                    timestamp=time.time()
                )
    
    def run_round(self) -> bool:
        """
        Execute one reconciliation round
        
        Returns:
            True if converged, False otherwise
        """
        self.round_num += 1
        round_messages: List[Message] = []
        
        # Phase 1: Each agent broadcasts SUMMARY to fanout peers
        for agent in self.agents:
            peers = self._select_peers(agent.agent_id)
            agent.peers = peers
            
            if agent.is_byzantine():
                msg = self._byzantine_agent_summary(agent)
            else:
                msg = self._honest_agent_summary(agent)
            
            # Send to selected peers
            for peer_id in peers:
                msg_copy = Message(
                    sender=msg.sender,
                    receiver=peer_id,
                    msg_type=msg.msg_type,
                    view=msg.view,
                    round_num=msg.round_num
                )
                round_messages.append(msg_copy)
                agent.messages_sent += 1
                self.total_messages += 1
        
        # Phase 2: Agents handle received messages
        for msg in round_messages:
            receiver = self.agents[msg.receiver]
            self._handle_summary(receiver, msg)
        
        # Check convergence
        return self.check_convergence()
    
    def check_convergence(self) -> bool:
        """Check if all honest agents have converged to ledger view"""
        honest_agents = [a for a in self.agents if not a.is_byzantine()]
        
        for agent in honest_agents:
            if agent.local_view != self.ledger_view:
                return False
        
        if self.convergence_round is None:
            self.convergence_round = self.round_num
        
        return True
    
    def run_until_convergence(self, max_rounds: int = 50) -> Dict:
        """
        Run protocol until convergence or max rounds
        
        Returns:
            Statistics dictionary
        """
        converged = False
        
        for _ in range(max_rounds):
            converged = self.run_round()
            if converged:
                break
        
        return self.get_statistics()
    
    def get_statistics(self) -> Dict:
        """Return statistics from simulation"""
        honest_agents = [a for a in self.agents if not a.is_byzantine()]
        
        return {
            'n_agents': self.n_agents,
            'f_byzantine': self.f_byzantine,
            'fanout': self.fanout,
            'rounds': self.round_num,
            'converged': self.convergence_round is not None,
            'convergence_round': self.convergence_round,
            'total_messages': self.total_messages,
            'total_ledger_queries': self.total_ledger_queries,
            'avg_messages_per_agent': self.total_messages / self.n_agents,
            'avg_ledger_queries_per_agent': self.total_ledger_queries / self.n_agents,
            'honest_agents': len(honest_agents),
            'byzantine_agents': self.f_byzantine
        }


def run_experiment(
    n_values: List[int],
    f_ratios: List[float],
    fanout: int,
    trials: int = 10
) -> List[Dict]:
    """
    Run experimental evaluation
    
    Args:
        n_values: List of network sizes to test
        f_ratios: List of Byzantine ratios (e.g., [0, 0.1, 0.2, 0.3])
        fanout: Fanout parameter
        trials: Number of trials per configuration
    
    Returns:
        List of result dictionaries
    """
    results = []
    
    for n in n_values:
        for f_ratio in f_ratios:
            f = int(n * f_ratio)
            
            # Ensure f < n/3 (BFT bound)
            if f >= n / 3:
                continue
            
            print(f"Running n={n}, f={f} ({f_ratio*100:.0f}% Byzantine)")
            
            trial_results = []
            for trial in range(trials):
                network = BFTMVDIDNetwork(
                    n_agents=n,
                    f_byzantine=f,
                    fanout=fanout
                )
                
                stats = network.run_until_convergence(max_rounds=50)
                stats['trial'] = trial
                trial_results.append(stats)
            
            # Aggregate results
            avg_convergence = sum(
                r['convergence_round'] for r in trial_results if r['converged']
            ) / len([r for r in trial_results if r['converged']])
            
            result = {
                'n': n,
                'f': f,
                'f_ratio': f_ratio,
                'fanout': fanout,
                'trials': trials,
                'convergence_rate': sum(r['converged'] for r in trial_results) / trials,
                'avg_convergence_round': avg_convergence if avg_convergence == avg_convergence else None,
                'avg_total_messages': sum(r['total_messages'] for r in trial_results) / trials,
                'avg_ledger_queries': sum(r['total_ledger_queries'] for r in trial_results) / trials,
                'trial_results': trial_results
            }
            results.append(result)
    
    return results


if __name__ == "__main__":
    # Quick test
    print("BFT-MV-DID Protocol Simulation")
    print("=" * 50)
    
    network = BFTMVDIDNetwork(n_agents=20, f_byzantine=6, fanout=5)
    stats = network.run_until_convergence()
    
    print(f"Network size: {stats['n_agents']}")
    print(f"Byzantine agents: {stats['f_byzantine']}")
    print(f"Converged: {stats['converged']}")
    print(f"Rounds to convergence: {stats['convergence_round']}")
    print(f"Total messages: {stats['total_messages']}")
    print(f"Total ledger queries: {stats['total_ledger_queries']}")
