import sys
sys.path.insert(0, r"E:\AkStudio\AkRepoManager")
from ak_repo_manager.config_store import ConfigStore
from ak_repo_manager.repo_scanner import scan_config

nodes = scan_config(ConfigStore().data)
flat = []

def walk(node, depth=0):
    flat.append((depth, node.name, node.category, len(node.children)))
    for child in node.children:
        walk(child, depth + 1)

for node in nodes:
    walk(node)

print("count", len(flat))
for depth, name, category, children in flat:
    print("  " * depth + f"{name} [{category}] children={children}")
