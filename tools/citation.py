# """Wetterdienst - Open weather data for humans"""
# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from pathlib import Path

import tomli
import yaml
from cff_from_621.lib import generate_cff_contents
from cffconvert import Citation
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).parent.parent
PYPROJECT_TOML = Path(ROOT / "pyproject.toml")
CFF = Path(ROOT / "CITATION.cff")


log = logging.getLogger(__name__)


def generate_cff_file(width: int = 79):
    """Almost similar to
    https://github.com/delb-xml/cff-from-621/blob/1fd6dcd1077fed0eac91fc427a1ca76bb48bebcd/cff_from_621/lib.py#L40
    """
    content = Path(ROOT / "pyproject.toml").read_text()
    raw = tomli.loads(content)
    config = {"project": raw["tool"]["poetry"]}
    config["project"]["authors"] = [{"name": author.split("<")[0][:-1]} for author in config["project"]["authors"]]
    cff_contents = generate_cff_contents(pyproject_contents=config, pyproject_path=PYPROJECT_TOML)
    cff_contents["message"] = "If you use this software, please cite it using these metadata."
    cff_serialisat = yaml.dump(
        allow_unicode=True,
        data=cff_contents,
        default_flow_style=False,
        explicit_start=True,
        explicit_end=True,
        indent=2,
        sort_keys=False,
        width=width,
    )
    try:
        Citation(cffstr=cff_serialisat).validate()
    except ValidationError as e:
        log.warning(e)
        raise SystemExit(1) from e
    CFF.write_text(data=cff_serialisat)


if __name__ == "__main__":
    generate_cff_file()
