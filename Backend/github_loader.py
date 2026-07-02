from git import Repo
import os
import shutil


class GitHubLoader:

    def __init__(self):
        self.base_path = "repositories"

    def clone_repo(self, repo_url):

        repo_name = repo_url.rstrip("/").split("/")[-1]

        clone_path = os.path.join(self.base_path, repo_name)

        # Delete old copy if it already exists
        if os.path.exists(clone_path):
            shutil.rmtree(clone_path)

        Repo.clone_from(repo_url, clone_path)

        return clone_path