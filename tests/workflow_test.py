from dotenv import load_dotenv

from workflows.workflow_orchestrator import (
    WorkflowOrchestrator,
)

load_dotenv()

orchestrator = WorkflowOrchestrator()

task = orchestrator.execute("Create a TypeScript email validator.")

print()
print("=" * 80)
print("GENERATED CODE")
print("=" * 80)
print(repr(task.generated_code))

print()
print("=" * 80)
print("ARCHITECT REVIEW")
print("=" * 80)
print(repr(task.architecture_review))

print()
print("=" * 80)
print("TESTS")
print("=" * 80)
print(repr(task.generated_tests))
