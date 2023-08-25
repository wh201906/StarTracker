import git, os

source_repo_path = "./test"
target_repo_path = "./output"


def has_changes(diff_result: git.DiffIndex):
    # cannot handle commit with no parents/multiple parents
    return len(diff_result) > 0


def has_only_additions(diff_result: git.DiffIndex):
    for diff_item in diff_result:
        lines = diff_item.diff.decode("utf-8").splitlines()
        if lines and lines[0].startswith("@@"):
            lines.pop(0)
        for line in lines:
            if line.startswith(" "):
                continue
            elif not line.startswith("+"):
                return False

    return True


# os.makedirs(target_repo_path)
# target_repo = git.Repo().init(target_repo_path)
source_repo = git.Repo(source_repo_path)
# source_repo.git.execute("git checkout --orphan shrinked")

commit_list = []
new_commit_idx = 0
new_commit_list = []

is_addition_last = True
for commit in source_repo.iter_commits(reverse=True):
    new_commit = False

    # cannot handle commit with no parents/multiple parents
    parents_num = len(commit.parents)
    if parents_num > 1:
        print(f"Error: parents num is {parents_num} rather than 1")
        continue
    elif parents_num == 0:
        is_addition_last = True
    else:
        diff_result = commit.diff(commit.parents[0], create_patch=True, R=True)
        if not has_changes(diff_result):
            new_commit = False
            # if it's the last commit?
        elif has_only_additions(diff_result):
            new_commit = not is_addition_last
            is_addition_last = True
        else:
            new_commit = True
            is_addition_last = False
        if new_commit:
            new_commit_list.append(new_commit_idx - 1)
        print(
            commit.hexsha,
            has_changes(diff_result),
            has_only_additions(diff_result),
            new_commit,
        )
    commit_list.append((commit.hexsha, new_commit))
    new_commit_idx += 1

print(commit_list)
print(new_commit_list)

commit_list[0]=(commit_list[0][0], True)
last_item = commit_list[0]
source_repo.git.checkout("-b", "shrinked", commit_list[0][0])
for commit_item in commit_list[1:]:
    print(commit_item, last_item)
    if commit_item[1] == True or last_item[1] == True:
        commit_for_info = source_repo.commit(last_item[0])
        source_repo.index.commit(
            "Test",
            author=commit_for_info.author,
            committer=commit_for_info.committer,
            author_date=commit_for_info.authored_datetime,
            commit_date=commit_for_info.committed_datetime,
        )
    last_item = commit_item
    source_repo.git.execute(
        f"git cherry-pick --allow-empty --no-commit {commit_item[0]}"
    )


# source_repo.git.execute("git checkout --orphan shrinked")
# source_repo.git.execute("git reset")
# source_repo.git.execute("git clean -f")
# start = commit_list[0][0]
# for commit_idx in new_commit_list:
#     print(commit_idx, commit_list[commit_idx])
#     source_repo.git.execute(f"git cherry-pick {start}..{commit_list[commit_idx][0]} --allow-empty")
#     start = commit_list[commit_idx][0]
# # curr.parent=0: initial commit(treat as add)
# # else
# # curr = unchanged: merge
# # curr = add, last != add, new
# # curr = add, last = add, merge
# # curr
