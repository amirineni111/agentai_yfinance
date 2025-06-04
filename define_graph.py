from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END

# Reducer: used to accumulate messages across graph states
def add_messages(a, b):
    return a + b

# Define the graph state structure
class State(TypedDict):
    messages: Annotated[list, add_messages]
    stock: str

# Initialize the graph builder
graph_builder = StateGraph(State)
