import enum


class Intent(str, enum.Enum):
    create_task = "create_task"
    list_tasks = "list_tasks"
    complete_task = "complete_task"
    delete_task = "delete_task"
    update_task = "update_task"
    compound_action = "compound_action"
    greeting = "greeting"
    thanks = "thanks"
    set_name = "set_name"
    unknown = "unknown"
