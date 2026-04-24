

def attach_total_cpu(processes, children):
    pass # compute subtree cpu for all processes

def get_top_origin(processes):
    pass # return process with highest total_cpu

def format_insight(p):
    return f"[Insight] Top CPU origin → {p.comm} (PID {p.pid}) | {p.total_cpu:.1f}% total CPU"
