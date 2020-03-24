import setuptools


with open("README.md", "r", encoding="utf-8") as file:
    long_description = file.read()

setuptools.setup(
    name="oh-my-ddl-shu",
    version="0.1",
    author="hwenwur",
    author_email="pypi@qiren.org",
    description="A tool to collect deadline in SHU.",
    lone_description=long_description,
    url="https://github.com/hwenwur/oh-my-ddl",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GPL License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
    install_requires=[
        "lxml",
        "requests",
        "tabulate"
    ],
    entry_points={
        "console_scripts":[
            "ohmyddl=ohmyddl.__main__:main"
        ]
    }
)
