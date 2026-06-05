#!/usr/bin/env python3
"""
Grade eval outputs against assertions
"""
import json
import os
import re
from pathlib import Path

def check_assertion(assertion, file_content, file_path):
    """Check single assertion against file content"""
    assertion_type = assertion.get('type')
    content = assertion.get('content')
    target = assertion.get('target')

    # Check if target file matches
    if target and not file_path.endswith(target):
        return None  # Skip, wrong file

    if assertion_type == 'contains':
        return content in file_content
    elif assertion_type == 'regex':
        return bool(re.search(content, file_content))
    elif assertion_type == 'not_contains':
        return content not in file_content

    return False

def grade_eval(eval_dir, eval_metadata):
    """Grade single eval directory"""
    results = []
    outputs_dir = eval_dir / 'with_skill' / 'outputs'

    if not outputs_dir.exists():
        return {'error': f'Outputs directory not found: {outputs_dir}'}

    # Read all output files
    output_files = {}
    for f in outputs_dir.iterdir():
        if f.is_file():
            try:
                output_files[f.name] = f.read_text()
            except:
                output_files[f.name] = ''

    # Check assertions
    for assertion in eval_metadata.get('assertions', []):
        target = assertion.get('target')
        file_content = output_files.get(target, '')

        passed = check_assertion(assertion, file_content, target)
        if passed is not None:
            results.append({
                'text': assertion.get('name', 'unknown'),
                'passed': passed,
                'evidence': f"Checked {target}" if passed else f"Failed: {target}"
            })

    return {'expectations': results}

def main():
    # Relative paths from kora-telemetry/scripts/
    scripts_dir = Path(__file__).parent
    kora_dir = scripts_dir.parent.parent  # 
    workspace = kora_dir.parent / 'KORA' / 'kora-telemetry-workspace' / 'iteration-1'
    evals_file = scripts_dir.parent / 'evals' / 'evals.json'

    if not workspace.exists():
        print(f"Note: Workspace not found: {workspace}")
        print("This script is intended to be run during eval execution.")
        print("The workspace directory is created when evals are executed.")
        return

    if not evals_file.exists():
        print(f"Error: Evals file not found: {evals_file}")
        return

    with open(evals_file) as f:
        evals_data = json.load(f)

    evals_by_name = {e['name']: e for e in evals_data['evals']}

    for eval_dir in workspace.iterdir():
        if not eval_dir.name.startswith('eval-'):
            continue

        # Find eval name from metadata
        metadata_file = eval_dir / 'eval_metadata.json'
        if not metadata_file.exists():
            continue

        with open(metadata_file) as f:
            metadata = json.load(f)

        eval_name = metadata.get('eval_name', '')
        eval_metadata = evals_by_name.get(eval_name, {'assertions': []})

        # Grade
        results = grade_eval(eval_dir, eval_metadata)

        # Save grading.json
        grading_file = eval_dir / 'with_skill' / 'grading.json'
        grading_file.parent.mkdir(parents=True, exist_ok=True)
        with open(grading_file, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"Graded {eval_name}: {len(results.get('expectations', []))} assertions")

if __name__ == '__main__':
    main()
