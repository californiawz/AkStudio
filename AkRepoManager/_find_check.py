import sys
from pathlib import Path
sys.path.insert(0, r"E:\AkStudio\AkRepoManager")
from ak_repo_manager.repo_scanner import _find_nested_gitmodules, norm, read_gitmodules
root = Path(r"E:\AkStudio")
excluded = {norm(root / m['path']) for m in read_gitmodules(root)}
print('excluded', len(excluded))
for p in sorted(_find_nested_gitmodules(root, excluded, 50)):
    print(p)
