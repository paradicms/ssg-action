#!/usr/bin/env python3
import dataclasses
import os.path
from dataclasses import dataclass
from pathlib import Path
from typing import Type

from configargparse import ArgParser

from paradicms_etl.github_action import GitHubAction
from paradicms_ssg.deployers.fs_deployer import FsDeployer
from paradicms_ssg.loaders.app_loader import AppLoader


class Action(GitHubAction):
    """
    Generate a static site using Paradicms.
    """

    @dataclass(frozen=True)
    class Inputs(GitHubAction.Inputs):
        build_directory_path: str = dataclasses.field(
            default="_site",
            metadata={
                "description": "Path to a directory where the generated static assets (CSS, HTML, JavaScript) should be placed"
            },
        )

        data_file_paths: str = dataclasses.field(
            default=GitHubAction.Inputs.REQUIRED,
            metadata={"description": "Colon-separated paths to one or more data files"},
        )

    def __init__(
        self, *, build_directory_path: str, data_file_paths: str, dev: bool, **kwds
    ):
        GitHubAction.__init__(self, **kwds)
        self.__build_directory_path = Path(build_directory_path)
        self.__data_file_paths = (
            tuple(
                Path(data_file_path)
                for data_file_path in data_file_paths.split(os.path.pathsep)
            )
            if data_file_paths
            else ()
        )
        self.__dev = dev

    @classmethod
    def _add_arguments(
        cls, arg_parser: ArgParser, *, inputs_class: Type[GitHubAction.Inputs]
    ):
        GitHubAction._add_arguments(arg_parser, inputs_class=cls.Inputs)

        arg_parser.add_argument(
            "--dev",
            action="store_true",
            help="start the app in dev mode rather than building it",
        )

    def _run(self):
        loader = AppLoader(
            data_file_paths=self.__data_file_paths,
            deployer=FsDeployer(
                # We're running in an environment that's never been used before, so no need to archive
                archive=False,
                # We're also running in Docker, which usually means that the GUI's out directory is on a different mount
                # than the directory we're "deploying" to, and we need to use copy instead of rename.
                copy=True,
                deploy_dir_path=Path(self.__build_directory_path).absolute(),
            ),
            dev=self.__dev,
            loaded_data_dir_path=self._data_dir_path / "loaded",
            pipeline_id=self._pipeline_id,
        )
        loader(flush=True, models=tuple())


if __name__ == "__main__":
    Action.main()
