"""
Main Experiment Runner
Generates all data for paper evaluation (Section 10)
"""

import sys
import json
import pickle
from pathlib import Path

# Add simulation modules to path
sys.path.append(str(Path(__file__).parent / 'simulations'))

from bft_mv_did_protocol import run_experiment as run_mv_experiment
from bft_sh_did_experiments import (
    BFTSHDIDExperiment,
    run_comparison_with_baselines
)


def run_all_experiments(output_dir: str = "results"):
    """
    Run all experiments for the paper evaluation
    
    Generates data for:
    - BFT-SH-DID gas costs (Experiment 1)
    - BFT-SH-DID end-to-end latency (Experiment 2)
    - BFT-MV-DID convergence time (Experiment 3)
    - BFT-MV-DID communication overhead (Experiment 4)
    - Baseline comparisons
    """
    
    Path(output_dir).mkdir(exist_ok=True)
    results = {}
    
    print("=" * 70)
    print("RUNNING ALL EXPERIMENTS FOR PAPER EVALUATION")
    print("=" * 70)
    
    # =========================================================================
    # BFT-SH-DID EXPERIMENTS
    # =========================================================================
    print("\n" + "="*70)
    print("PART 1: BFT-SH-DID (Self-Healing Recovery)")
    print("="*70)
    
    sh_experiment = BFTSHDIDExperiment()
    
    # Experiment 1: Gas Cost vs. Quorum Size
    print("\n[Experiment 1] Gas Cost Analysis")
    print("-" * 70)
    f_values = [1, 2, 3, 5, 10, 15]  # Test various f values
    gas_results = sh_experiment.run_gas_cost_analysis(
        f_values=f_values,
        trials=20
    )
    results['sh_did_gas_costs'] = gas_results
    
    print("\nGas Cost Summary:")
    for r in gas_results:
        print(f"  f={r['f']:2d} (quorum={r['quorum_size']:2d}): {r['avg_gas']:7,.0f} gas")
    
    # Save intermediate results
    with open(f"{output_dir}/sh_did_gas_costs.json", 'w') as f:
        json.dump(gas_results, f, indent=2, default=str)
    
    # Experiment 2: End-to-End Latency (Normal vs. Adversarial)
    print("\n[Experiment 2] End-to-End Latency Analysis")
    print("-" * 70)
    latency_results = sh_experiment.run_latency_analysis(
        n_watchers=10,  # 3*3+1
        f_byzantine=3,
        behaviors=["none", "delay"],
        trials=30
    )
    results['sh_did_latency'] = latency_results
    
    print("\nLatency Summary:")
    for r in latency_results:
        if r['success_rate'] > 0:
            print(f"  {r['behavior']:10s}: {r['avg_total_latency']:.1f}s " +
                  f"({r['avg_total_latency']/60:.1f} min) [success: {r['success_rate']*100:.0f}%]")
    
    with open(f"{output_dir}/sh_did_latency.json", 'w') as f:
        json.dump(latency_results, f, indent=2, default=str)
    
    # Experiment 3: Comparison with Baselines
    print("\n[Experiment 3] Baseline Comparison")
    print("-" * 70)
    comparison = run_comparison_with_baselines()
    results['baseline_comparison'] = comparison
    
    print("\nComparison:")
    for system, data in comparison['baselines'].items():
        print(f"  {data['name']:30s}: {data['gas']:7,} gas, " +
              f"latency={data['latency']/60:.1f}min, BFT={data['bft_guarantees']}")
    
    ours = comparison['bft_sh_did']
    print(f"  {ours['name']:30s}: {ours['gas']:7,} gas, " +
          f"latency={ours['latency']/60:.1f}min, BFT={ours['bft_guarantees']}")
    
    with open(f"{output_dir}/baseline_comparison.json", 'w') as f:
        json.dump(comparison, f, indent=2, default=str)
    
    # =========================================================================
    # BFT-MV-DID EXPERIMENTS
    # =========================================================================
    print("\n" + "="*70)
    print("PART 2: BFT-MV-DID (Multi-View Reconciliation)")
    print("="*70)
    
    # Experiment 4: Convergence Time vs. Network Size
    print("\n[Experiment 4] Convergence Analysis - Network Size")
    print("-" * 70)
    n_values = [10, 20, 30, 50, 100]
    f_ratios = [0.0, 0.1, 0.2]  # 0%, 10%, 20% Byzantine
    fanout = 5
    
    convergence_results = run_mv_experiment(
        n_values=n_values,
        f_ratios=f_ratios,
        fanout=fanout,
        trials=10
    )
    results['mv_did_convergence'] = convergence_results
    
    print("\nConvergence Summary:")
    for r in convergence_results:
        if r['convergence_rate'] > 0:
            print(f"  n={r['n']:3d}, f={r['f']:2d} ({r['f_ratio']*100:.0f}%): " +
                  f"{r['avg_convergence_round']:.1f} rounds [rate: {r['convergence_rate']*100:.0f}%]")
    
    with open(f"{output_dir}/mv_did_convergence.json", 'w') as f:
        json.dump(convergence_results, f, indent=2, default=str)
    
    # Experiment 5: Communication Overhead
    print("\n[Experiment 5] Communication Overhead Analysis")
    print("-" * 70)
    # Already captured in convergence_results
    
    print("\nCommunication Overhead Summary:")
    for r in convergence_results:
        print(f"  n={r['n']:3d}, f={r['f']:2d}: " +
              f"{r['avg_total_messages']:.0f} msgs, " +
              f"{r['avg_ledger_queries']:.1f} queries")
    
    # =========================================================================
    # SAVE ALL RESULTS
    # =========================================================================
    print("\n" + "="*70)
    print("SAVING RESULTS")
    print("="*70)
    
    # Save complete results as pickle (preserves all data)
    with open(f"{output_dir}/all_results.pkl", 'wb') as f:
        pickle.dump(results, f)
    
    # Save summary as JSON
    summary = {
        'sh_did_gas_summary': [
            {
                'f': r['f'],
                'quorum': r['quorum_size'],
                'gas': r['avg_gas']
            } for r in gas_results
        ],
        'sh_did_latency_summary': [
            {
                'behavior': r['behavior'],
                'latency_seconds': r['avg_total_latency'],
                'success_rate': r['success_rate']
            } for r in latency_results
        ],
        'mv_did_convergence_summary': [
            {
                'n': r['n'],
                'f': r['f'],
                'rounds': r['avg_convergence_round'],
                'messages': r['avg_total_messages']
            } for r in convergence_results
        ]
    }
    
    with open(f"{output_dir}/summary.json", 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"\nAll results saved to: {output_dir}/")
    print(f"  - all_results.pkl (complete data)")
    print(f"  - summary.json (high-level summary)")
    print(f"  - Individual JSON files for each experiment")
    
    print("\n" + "="*70)
    print("EXPERIMENT COMPLETE!")
    print("="*70)
    print("\nNext steps:")
    print("  1. Run: python generate_figures.py")
    print("  2. Check: results/figures/ for all paper figures")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run all experiments for paper evaluation')
    parser.add_argument('--output-dir', default='results', help='Output directory')
    
    args = parser.parse_args()
    
    results = run_all_experiments(output_dir=args.output_dir)
