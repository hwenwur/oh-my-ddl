import setuptools
import ohmyddl
import pathlib


with open("README.md", "r", encoding="utf-8") as file:
    long_description = file.read()


webroot = pathlib.Path("ohmyddl/webroot")
webroot_data = [str(x)[8:] for x in webroot.glob("**/*")]


setuptools.setup(
    name="ohmyddl",
    version=ohmyddl.__version__,
    author="hwenwur",
    author_email="pypi@qiren.org",
    description="A tool to collect deadline in SHU.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hwenwur/oh-my-ddl",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        "lxml",
        "requests",
    ],
    entry_points={
        "console_scripts":[
            "ohmyddl-cli=ohmyddl.__main__:main",
            "ohmyddl=ohmyddl.__main__:web"
        ]
    },
    include_package_data=True,
    package_data = {
        "ohmyddl": webroot_data
    }
)
