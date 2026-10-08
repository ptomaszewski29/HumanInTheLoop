from dotenv import load_dotenv

from workflows.workflow_orchestrator import (
    WorkflowOrchestrator,
)

load_dotenv()

orchestrator = WorkflowOrchestrator()

task = orchestrator.execute("Create a TypeScript email validator.")

print()
print("=" * 80)
print("GENERATED FILES")
print("=" * 80)
for item in task.generated_files:
    print(f"  [{item.file_type.value}] {item.path}")

print()
print("=" * 80)
print("ARCHITECT REVIEW")
print("=" * 80)
print(repr(task.architecture_review))


