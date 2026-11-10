from agent_runtime.session.model import Session

def calculator(ctx: Session, expression: str):
    return eval(expression)  # 教学用。真实项目必须换成安全求值，后面会讲为什么

def echo(ctx: Session, text: str):
    return text


def weather(ctx: Session, city: str):
    return f"{city}的天气是：晴天"


def todo_add(ctx: Session, item: str):
    ctx.todos.append(item)
    return f"已添加待办事项：{item}"


def todo_list(ctx: Session):
    if not ctx.todos:
        return "待办事项列表为空"
    return "\n".join(f"{i+1}. {t}" for i, t in enumerate(ctx.todos))

