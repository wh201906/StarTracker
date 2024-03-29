import git, sys

SOURCE_REPO_PATH = "./test"
TARGET_BRANCH_NAME = "shrinked"


def has_changes(diff_result: git.DiffIndex):
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


repo = git.Repo(SOURCE_REPO_PATH)

commit_list = []

print("Checking commits")
last_commit_type = "add"
is_addition_last = True
for commit in repo.iter_commits(reverse=True):
    # new_commit: the previous commit should be picked
    new_commit = False

    # cannot handle commit with no parents/multiple parents
    parents_num = len(commit.parents)
    if parents_num > 1:
        print(f"Error: parents num is {parents_num} rather than 1")
        sys.exit(0)
    elif parents_num == 0:  # the first commit
        last_commit_type = "add"  # OK if the first commit is empty
    else:  # parents_num == 1
        diff_result = commit.diff(commit.parents[0], create_patch=True, R=True)
        additions_only = has_only_additions(diff_result)
        changed = has_changes(diff_result)
        if last_commit_type == "empty":  # shrink empty commits
            new_commit = False
        elif last_commit_type == "add":
            # shrink continuous addition-only commits
            new_commit = False if (not changed) or additions_only else True
        elif last_commit_type == "del":  # always pick commits with deletions
            new_commit = True

        # update last state
        if not changed:
            last_commit_type = "empty"
        elif additions_only:
            last_commit_type = "add"
        else:
            last_commit_type = "del"

    commit_list.append((commit.hexsha, new_commit))

commit_num = len(commit_list)
if commit_num < 2:
    print(f"Error: this repo has only {commit_num} commit(s)")
    sys.exit(0)
print(f"{commit_num} commits")
commit_list.append(("end", True))  # pick the last commit

print("Shrinking commits")
new_commit_num = 0
shrinked_commit_num = 0
last_item = commit_list[0]
# the first commit is always picked
# otherwise the `git cherry-pick` won't work
repo.git.checkout("-b", TARGET_BRANCH_NAME, commit_list[0][0])
for commit_item in commit_list[1:]:
    if commit_item[1] == True:
        commit_for_info = repo.commit(last_item[0])
        repo.index.commit(
            f"{shrinked_commit_num} Shrinked",
            author=commit_for_info.author,
            committer=commit_for_info.committer,
            author_date=commit_for_info.authored_datetime,
            commit_date=commit_for_info.committed_datetime,
        )
        new_commit_num += 1
        shrinked_commit_num = 0
    last_item = commit_item

    if commit_item[0] == "end":
        break
    repo.git.execute(f"git cherry-pick --allow-empty --no-commit {commit_item[0]}")
    shrinked_commit_num += 1

print(f"{commit_num} commits -> {new_commit_num + 1} commits")
