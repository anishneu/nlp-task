import enum


class Intent(str, enum.Enum):
    create_task = "create_task"
    list_tasks = "list_tasks"
    complete_task = "complete_task"
    delete_task = "delete_task"
    greeting = "greeting"
    set_name = "set_name"
    unknown = "unknown"
