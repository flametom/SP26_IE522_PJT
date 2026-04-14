#!/bin/bash
#SBATCH --job-name=pmax_ext
#SBATCH --array=0-35
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --account=open
#SBATCH --partition=open
#SBATCH --output=results/pmax_extension/slurm_%A_%a.log
#
# Extended Pmax experiment — PSU ROAR
# 36 tasks: 12 Pmax × 3 Hmax, each runs 10 seeds serially
#
# Submit:     sbatch run_pmax_extension.sbatch
# Monitor:    squeue -u jqb6679
# After done: python run_pmax_extension.py --merge

mkdir -p results/pmax_extension

module load anaconda
source activate /storage/work/jqb6679/ie522

cd "$SLURM_SUBMIT_DIR"

echo "=== Task $SLURM_ARRAY_TASK_ID  $(date) ==="
python run_pmax_extension.py --task-id "$SLURM_ARRAY_TASK_ID"
echo "=== Done  $(date) ==="
