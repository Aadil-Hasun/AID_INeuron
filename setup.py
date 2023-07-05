from setuptools import setup, find_packages
from typing import List
import os

HYPHEN_E_DOT = "-e ."
CUR_PATH = os.path.curdir


def get_requirements(file_path: str) -> List[str]:
    requirements = []
    with open(file_path, "r") as file:
        requirements = file.readlines()
        requirements = [requirement.replace("\n", "") for requirement in requirements]

        if HYPHEN_E_DOT in requirements:
            requirements.remove(HYPHEN_E_DOT)

    return requirements

setup(
    name="ImageDownloader",
    version="0.0.1",
    author="Aadil",
    author_email="aadilhasun@gmail.com",
    install_requires=get_requirements(os.path.join(CUR_PATH, "requirements.txt")),
    packages=find_packages()
)
