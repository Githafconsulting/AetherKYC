from nodes.ack_control_center_node import ack_control_center
#from nodes.send_to_kyc_node import send_to_kyc
from model.state import IngestionState
from langgraph.graph import StateGraph, START, END

# Build graph
graph_builder = StateGraph(IngestionState)

# Nodes
graph_builder.add_node("ack", ack_control_center)
#graph_builder.add_node("kyc", send_to_kyc)

# Edges
graph_builder.add_edge(START, "ack")
graph_builder.add_edge("ack", END)

# Compile
graph = graph_builder.compile()
