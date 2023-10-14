#!/usr/bin/env python3
import dataclasses
import os.path
from dataclasses import dataclass
from pathlib import Path
from typing import List

from more_itertools import consume
from paradicms_etl.extractors.rdf_file_extractor import RdfFileExtractor
from paradicms_etl.github_action import GitHubAction
from paradicms_etl.transformers.rdf_conjunctive_graph_transformer import (
    RdfConjunctiveGraphTransformer,
)
from paradicms_etl.utils.merge_same_as_models import merge_same_as_models
from paradicms_ssg.deployers.fs_deployer import FsDeployer
from paradicms_ssg.model_standardizer import model_standardizer
from paradicms_ssg.models.root_model_classes_by_name import ROOT_MODEL_CLASSES_BY_NAME
from paradicms_ssg.static_site_generator import StaticSiteGenerator


class Action(GitHubAction):
    """
    Generate a static site using Paradicms.
    """

    @dataclass(frozen=True)
    class Inputs(GitHubAction.Inputs):
        client_api: str = dataclasses.field(
            default="",
            metadata={
                "description": "API to use on the client side, defaults to using static data"
            },
        )

        data_paths: str = dataclasses.field(
            default=".paradicms/data",
            metadata={
                "description": "colon-separated paths to one or more data files created by ETL actions, or directories containing data files"
            },
        )

        next_commands: str = dataclasses.field(
            default=",".join(StaticSiteGenerator.NEXT_COMMANDS_DEFAULT),
            metadata={
                "description": "comma-separated list of Next.js commands to execute"
            },
        )

        site_directory_path: str = dataclasses.field(
            default="_site",
            metadata={
                "description": "Path to a directory where the generated static assets (CSS, HTML, JavaScript) should be placed"
            },
        )

    def __init__(
        self,
        *,
        client_api: str,
        data_paths: str,
        next_commands: str,
        site_directory_path: str,
        **kwds,
    ):
        GitHubAction.__init__(self, **kwds)

        self.__client_api = client_api if client_api.strip() else None

        data_file_paths: List[Path] = []
        for data_path in data_paths.split(os.path.pathsep):
            data_path_ = Path(data_path)
            if not data_path_.exists():
                raise ValueError(f"data path {data_path_} does not exist")
            if data_path_.is_file():
                data_file_paths.append(data_path_)
            elif data_path_.is_dir():
                data_dir_path = data_path_
                for file_name in os.listdir(data_dir_path):
                    if not os.path.splitext(file_name)[-1].lower() == ".trig":
                        continue
                    data_file_paths.append(Path(data_dir_path / file_name))
            else:
                raise NotImplementedError
        self.__data_file_paths = tuple(data_file_paths)

        self.__next_commands = tuple(
            next_command.strip() for next_command in next_commands.split(",")
        )
        self.__site_directory_path = Path(site_directory_path)

    def _run(self):
        def extract_transform():
            for data_file_path in self.__data_file_paths:
                yield from RdfConjunctiveGraphTransformer(
                    root_model_classes_by_name=ROOT_MODEL_CLASSES_BY_NAME
                )(
                    **RdfFileExtractor(rdf_file_path=data_file_path)()  # type: ignore
                )  # type: ignore

        consume(
            StaticSiteGenerator(
                cache_dir_path=self._cache_dir_path,
                client_api=self.__client_api,
                deployer=FsDeployer(
                    # We're running in an environment that's never been used before, so no need to archive
                    archive=False,
                    # We're also running in Docker, which usually means that the GUI's out directory is on a different mount
                    # than the directory we're "deploying" to, and we need to use copy instead of rename.
                    copy=True,
                    deploy_dir_path=Path(self.__site_directory_path).absolute(),
                ),
                next_commands=self.__next_commands,
                pipeline_id=self._pipeline_id,
            )(
                flush=True,
                models=merge_same_as_models(model_standardizer(extract_transform())),
            )
        )


if __name__ == "__main__":
    Action.main()
