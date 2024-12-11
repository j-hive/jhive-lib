"""Settings ingestion and creation utility functions.
"""

# Imports


import shutil
import itertools
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Annotated, Literal, Self, Any

import yaml
from pydantic import (
    BaseModel,
    StringConstraints,
    NonNegativeInt,
    PositiveInt,
    PositiveFloat,
)

from . import logs, misc, science


# Constants


CONFIGURATION_FILE_KEY = "config"
"""Key of path to configuration YAML file.
"""


# Classes


class BaseSettings(BaseModel):
    """Base settings object model."""

    def to_dict(self) -> dict[str,]:
        return self.__dict__

    @staticmethod
    def get(key: str, **kwargs) -> Any | None:
        """Get the value for a setting from user input, preferring CLI-passed
        values over file-passed values.

        Parameters
        ----------
        key : str
            Name of setting.

        Returns
        -------
        Any | None
            Value of setting, if it is set by user, and None otherwise.
        """
        #
        if key in kwargs:
            return kwargs.get(key)

        #
        elif key.replace("_", " ") in kwargs:
            return kwargs.get(key.replace("_", " "))


class FICL(BaseSettings):
    """Settings for a single scientific observation.

    Corresponds to the field, image version, catalog version, and filter of the
    frame.

    Attributes
    ----------
    field : str
        Field of observation, as a lowercase string.
    image_version : str
        Image processing version, as a lowercase string.
    catalog_version : str
        Cataloging version, as a lowercase string.
    filter : str
        Filter name, as a lowercase string.
    pixscale : tuple[float, float]
        Pixel scale along x and y axes, respectively, in arcseconds per pixel,
        as a tuple of positive floats.
    objects : list[int]
        Integer IDs of galaxies or cluster targets as listed in this FICL's
        corresponding photometric catalog, as a list of positive integers, by
        default empty.
    failed : list[int]
        Integer IDs of objects which failed to run, as a list of positive
        integers, by default empty.
    """

    field: Annotated[str, StringConstraints(to_lower=True)]
    image_version: Annotated[str, StringConstraints(to_lower=True)]
    catalog_version: Annotated[str, StringConstraints(to_lower=True)]
    filter: Annotated[str, StringConstraints(to_lower=True)]
    pixscale: tuple[PositiveFloat, PositiveFloat]
    objects: list[PositiveInt]
    failed: list[PositiveInt] = []

    def __init__(self, **kwargs):
        # Validate required files
        catalog_path, science_path = kwargs.get("catalog"), kwargs.get("science")
        if (not isinstance(catalog_path, Path)) or (not catalog_path.is_file()):
            raise FileNotFoundError("photometric catalog missing")
        if (not isinstance(science_path, Path)) or (not science_path.is_file()):
            raise FileNotFoundError("science frame missing")

        #
        pixscale = science.get_pixscale(path=science_path)
        objects = misc.get_objects(
            path=catalog_path,
            process_id=kwargs.get("process_id"),
            process_count=kwargs.get("process_count"),
            objects=kwargs.get("objects"),
            first_object=kwargs.get("first_object"),
            last_object=kwargs.get("last_object"),
        )

        #
        model = {
            "field": kwargs.get("field"),
            "image_version": kwargs.get("image_version"),
            "catalog_version": kwargs.get("catalog_version"),
            "filter": kwargs.get("filter"),
            "pixscale": pixscale,
            "objects": objects,
        }

        #
        super().__init__(**model)

    def __str__(self) -> str:
        return "_".join(
            [self.field, self.image_version, self.catalog_version, self.filter]
        )

    def __eq__(self, other: Self) -> bool:
        return (isinstance(other, FICL)) and (str(self) == str(other))

    def to_dict(self) -> dict[str, str | list[int] | tuple[float, float]]:
        #
        model = {
            "field": self.field,
            "image version": self.image_version,
            "catalog version": self.catalog_version,
            "filter": self.filter,
            "pixscale": misc.get_str_from_pixscale(self.pixscale),
            "objects": self.objects,
            "failed": self.failed,
        }

        #
        return model

    def remove(self, objects: list[int]):
        """Remove objects from this FICL's configuration.

        Does nothing if an object is not in FICL's list.

        Parameters
        ----------
        objects : list[int]
            Integer IDs of objects to remove from FICL.
        """
        #
        for object in objects:
            #
            try:
                self.objects.remove(object)
                self.failed.append(object)

            #
            except:
                continue

    @staticmethod
    def get_sorted(ficls: list[Self]) -> list[Self]:
        """Get a list of FICLs, sorted by their filter wavelengths.

        Note this function assumes each FICL of same FIC.

        Parameters
        ----------
        ficls : list[FICL]
            List of FICLs to be sorted.

        Returns
        -------
        list[FICL]
            List of FICLs, sorted by filter wavelength, ascending.
        """
        # Get dict of FICLs indexed by their filter wavelength (e.g. 200 for f200w-clear)
        ficls_by_wavelength = {}
        for ficl in ficls:
            try:
                ficls_by_wavelength[int(re.findall(r"\d{3}", ficl.filter)[0])] = ficl
            except:
                pass

        # Get list of FICLs sorted by wavelength
        sorted_ficls = []
        for filter in sorted(ficls_by_wavelength):
            sorted_ficls.append(ficls_by_wavelength[filter])

        # Return list of FICLs
        return sorted_ficls

    @staticmethod
    def get(key: str, required: bool = True, **kwargs) -> list[int | str] | None:
        """Get the value for a FICLO setting from CLI and YAML kwargs.

        Parameters
        ----------
        key : str
            Name of setting to get.
        required : bool, optional
            Raise error if setting not found, by default True.

        Returns
        -------
        list[int | str] | None
            Setting, preferring CLI over YAML, if found.

        Raises
        ------
        KeyError
            Field, image version, catalog version, or filter missing.
        """
        #
        alt_key = key.replace("_", " ")

        #
        if key[:-1] in kwargs:
            return [kwargs[key[:-1]]]

        #
        elif key in kwargs:
            return kwargs[key]

        #
        elif alt_key[:-1] in kwargs:
            return [kwargs[alt_key[:-1]]]

        #
        elif alt_key in kwargs:
            return kwargs[alt_key]

        #
        elif required:
            raise KeyError(f"{alt_key} not found")


class StageSettings(BaseSettings):
    """Stages to run, as flags.

    Attributes
    ----------
    setup : bool
        Setup program run, by default True.
    product : bool
        Make product files, by default True.
    main : bool
        Run main program, by default True.
    cleanup : bool
        Remove failed files, by default True.
    """

    setup: bool = True
    product: bool = True
    main: bool = True
    cleanup: bool = True

    def __init__(self, **values):
        #
        model = {}

        #
        primitive_attributes = ["setup", "product", "main", "cleanup"]
        for attribute in primitive_attributes:
            ##
            attribute_value = self.get(key=attribute, **values)
            if attribute_value is not None:
                model[attribute] = attribute_value

        #
        super().__init__(**model)

    def to_dict(self) -> str | list[str]:
        #
        if all(self.__dict__.values()):
            return "all"

        #
        elif not any(self.__dict__.values()):
            return "none"

        #
        else:
            return [stage for stage, ran in self.__dict__.items() if ran]

    @staticmethod
    def get(key: str, **kwargs) -> bool | Self | None:
        """Get the value for a stage setting from user input, preferring
        CLI-passed values over file-passed values.

        Parameters
        ----------
        key : str
            Name of setting.

        Returns
        -------
        bool | Self | None
            Value of setting, if it is set by user, and None otherwise.
        """
        # Get setting from this or child class
        if key == "stages":
            ## This setting object has been made by a child class
            if (key in kwargs) and isinstance(kwargs.get(key), StageSettings):
                return kwargs.get(key)

            ## This setting object has not yet been made
            else:
                return StageSettings(**kwargs)

        # Get setting from CLI
        if f"skip_{key}" in kwargs:
            return not kwargs[f"skip_{key}"]

        # Get setting from YAML
        from_yaml = kwargs.get("stages")
        if from_yaml is not None:
            return (key in from_yaml) or ("all" in from_yaml)


class RemakeSettings(BaseSettings):
    """Files to remake and overwrite, as flags.

    Attributes
    ----------
    products : bool
        Remake product files, by default False.
    main : bool
        Remake main files, by default False.
    """

    products: bool = False
    main: bool = False

    def __init__(self, **values):
        #
        model = {}

        #
        primitive_attributes = ["products", "main"]
        for attribute in primitive_attributes:
            ##
            attribute_value = self.get(key=attribute, **values)
            if attribute_value is not None:
                model[attribute] = attribute_value

        #
        super().__init__(**model)

    def to_dict(self) -> str | list[str]:
        #
        if all(self.__dict__.values()):
            return "all"

        #
        elif not any(self.__dict__.values()):
            return "none"

        #
        else:
            return [file_type for file_type, remade in self.__dict__.items() if remade]

    @staticmethod
    def get(key: str, **kwargs) -> bool | Self | None:
        """Get the value for a remake setting from user input, preferring
        CLI-passed values over file-passed values.

        Parameters
        ----------
        key : str
            Name of setting.

        Returns
        -------
        bool | Self | None
            Value of setting, if it is set by user, and None otherwise.
        """
        # Get setting from this or child class
        if key == "remake":
            ## This setting object has been made by a child class
            if (key in kwargs) and isinstance(kwargs.get(key), RemakeSettings):
                return kwargs.get(key)

            ## This setting object has not yet been made
            else:
                return RemakeSettings(**kwargs)

        # Get setting from CLI
        if f"remake_{key}" in kwargs:
            return kwargs[f"remake_{key}"]

        # Get setting from YAML
        from_yaml = kwargs.get("remake")
        if (from_yaml is not None) and ((key in from_yaml) or ("all" in from_yaml)):
            return True


class RuntimeSettings(BaseSettings):
    """Settings for the runtime of a J-HIVE program.

    Attributes
    ----------
    date_time : datetime
        Date time at launch.
    process_id : int
        ID of process in batch, as a non-negative integer, by default 0.
    process_count : int
        Number of processes in batch, as a positive integer, by default 1.
    log_level : str
        Level at which to log, one of standard Python levels, by default 'info'.
    progress_bar : bool
        Display progress as a loading bar, by default False.
    stages : StageSettings
        Stages to run.
    remake : RemakeSettings
        Files to remake and overwrite.
    """

    date_time: datetime
    process_id: NonNegativeInt = 0
    process_count: PositiveInt = 1
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    progress_bar: bool = False
    stages: StageSettings
    remake: RemakeSettings

    def __init__(self, **values):
        #
        model = {"date_time": datetime.now()}

        #
        primitive_attributes = [
            "process_id",
            "process_count",
            "log_level",
            "progress_bar",
        ]
        for attribute in primitive_attributes:
            model |= get_value(key=attribute, **values)

        #
        model |= get_value(key="stages", cls=StageSettings, new=True, **values)
        model |= get_value(key="remake", cls=RemakeSettings, new=True, **values)

        #
        super().__init__(**model)

        #
        if self.process_id >= self.process_count:
            raise ValueError(
                f"process ID {self.process_id} > # processes {self.process_count}"
            )

    def to_dict(self) -> dict[str,]:
        #
        model = {
            "started": self.date_time,
            "verbosity": self.log_level,
            "progress": "show" if self.progress_bar else "hide",
        }

        #
        if self.process_count > 1:
            model["batch mode"] = {
                "process": self.process_id + 1,
                "out of": self.process_count,
            }

        #
        model["stages"] = self.stages.to_dict()
        model["remade"] = self.remake.to_dict()

        #
        return model

    def to_yaml(self, path: Path):
        yaml.dump(self.to_dict(), open(path, mode="a"), sort_keys=False)

    def setup_logs(self, path: Path) -> logging.Logger:
        return logs.setup(path=path, level=self.log_level)


class ScienceSettings(BaseSettings):
    """Settings for the scientific algorithms of a J-HIVE program.

    Attributes
    ----------
    minimum : int
        Minimum square image dimensions, in pixels, as a positive integer, by
        default 32.
    scale : float
        Multiplier on initial radius to determine image size, as a positive
        float, by default 20.0.
    ficls : list[FICL]
        FICLs over which to run program, by default empty.
    """

    minimum: PositiveInt = 32
    scale: PositiveFloat = 20.0
    ficls: list[FICL]

    def __init__(self, **values):
        #
        model = {"ficls": []}

        #
        primitive_attributes = ["minimum", "scale"]
        for attribute in primitive_attributes:
            model |= get_value(key=attribute, cls=ScienceSettings, **values)

        #
        ## NOTE Child classes of this class MUST pass these kwargs to the init
        ## function of its super class, for each FICL
        ## Catalog path object for FICL, with kw: "F_I_C_L_catalog"
        ## Science path object for FICL, with kw: "F_I_C_L_science"

        ##
        first_object = get_value(key="first_object", **values) | get_value(
            key="first", **values
        )
        last_object = get_value(key="last_object", **values) | get_value(
            key="last", **values
        )
        first_object = None if len(first_object) == 0 else first_object
        last_object = None if len(last_object) == 0 else last_object

        ficls_attributes = [
            "fields",
            "image_versions",
            "catalog_versions",
            "filters",
            "objects",
        ]
        ficls_model = [
            FICL.get(key=attribute, required=attribute != "objects", **values)
            for attribute in ficls_attributes
        ]

        ##
        runtime: RuntimeSettings = values.get("runtime")
        possible_ficls = itertools.product(*ficls_model[:-1])
        for possible_ficl in possible_ficls:
            ##
            try:
                ##
                ficl_str = "_".join(possible_ficl)

                ##
                if (f"{ficl_str}_catalog" not in values) or (
                    f"{ficl_str}_science" not in values
                ):
                    continue

                ##
                ficl_model = {
                    "field": possible_ficl[0],
                    "image_version": possible_ficl[1],
                    "catalog_version": possible_ficl[2],
                    "filter": possible_ficl[3],
                    "objects": ficls_model[-1],
                    "process_id": runtime.process_id,
                    "process_count": runtime.process_count,
                    "first_object": first_object,
                    "last_object": last_object,
                    "catalog": values.get(f"{ficl_str}_catalog"),
                    "science": values.get(f"{ficl_str}_science"),
                }

                ##
                model["ficls"].append(FICL(**ficl_model))

            ##
            except Exception as e:
                print(e)
                continue

        #
        super().__init__(**model)

    def to_dict(self) -> dict[str,]:
        #
        model = {"ficls": [], "minimum": self.minimum, "scale": self.scale}

        #
        for ficl in self.ficls:
            model["ficls"].append(ficl.to_dict())

        #
        return model

    def to_yaml(self, path: Path):
        yaml.dump(self.to_dict(), open(path, mode="a"), sort_keys=False)

    @staticmethod
    def get(key: str, **kwargs) -> Any | None:
        """Get the value for a science setting from user input, preferring
        CLI-passed values over file-passed values.

        Parameters
        ----------
        key : str
            Name of setting.

        Returns
        -------
        Any | None
            Value of setting, if it is set by user, and None otherwise.
        """
        # Get setting from CLI
        if key in kwargs:
            return kwargs[key]

        # Get setting from YAML
        if ("science" in kwargs) and (key in kwargs["science"]):
            return kwargs["science"][key]


class JHIVESettings(BaseSettings):
    """Settings for a J-HIVE program.

    Attributes
    ----------
    runtime : RuntimeSettings
        Settings for the runtime of a J-HIVE program.
    science : ScienceSettings
        Settings for the scientific algorithms of a J-HIVE program.
    """

    runtime: RuntimeSettings
    science: ScienceSettings

    def __init__(self, **kwargs):
        #
        model = {}

        #
        values = get_all_values(**kwargs)

        #
        model |= get_value(key="runtime", cls=RuntimeSettings, new=True, **values)
        model |= get_value(
            key="science", cls=ScienceSettings, new=True, **values | model
        )

        #
        super().__init__(**model)

    def to_dict(self) -> dict[str, dict[str,]]:
        """Represent settings object as a dict.

        Returns
        -------
        dict[str, dict[str,]]
            Dict representation of settings object.
        """
        #
        model = {
            "runtime": self.runtime.to_dict(),
            "science": self.science.to_dict(),
        }

        #
        return model

    def to_yaml(self, path: Path):
        """Record settings.

        Parameters
        ----------
        path : Path
            Path to which to write settings.
        """
        yaml.dump(self.to_dict(), open(path, mode="w"), sort_keys=False)

    def setup_dirs(self, dirs: list[Path]):
        """Make missing directories.

        Parameters
        ----------
        dirs : list[Path]
            Paths to required directories.
        """
        for dir in dirs:
            dir.mkdir(parents=True, exist_ok=True)

    def setup_logs(self, path: Path) -> logging.Logger:
        """Make missing loggers.

        Parameters
        ----------
        path : Path
            Path to which to output logs, in addition to STDOUT.

        Returns
        -------
        Logger
            Logging object.
        """
        return self.runtime.setup_logs(path=path)

    def cleanup_dirs(self, dirs: list[tuple[Path, list[str]]]):
        """Remove failed directories.

        Parameters
        ----------
        dirs : list[tuple[Path, list[str]]]
            List of (dir, list[file]) pairs, where the first item is a path to a
            directory, and the second item is a list of filenames required to
            exist in the directory. If any required files are not found, the
            directory is removed.
        """
        for dir, files in dirs:
            found = [child.name for child in dir.iterdir()]

            for file in files:
                if file not in found:
                    shutil.rmtree(dir, ignore_errors=True)
                    break


# Functions


def get_all_values(**kwargs) -> dict[str,]:
    """Get values for all settings configured by user, preferring CLI-passed
    values over file-passed values, as a dict.

    Returns
    -------
    dict[str,]
        Dict from setting names to their values, as set by the user, preferring
        CLI-passed values over file-passed values.
    """
    # Get values for settings from file
    try:
        config_path = misc.get_path_object(kwargs[CONFIGURATION_FILE_KEY])
        values = yaml.safe_load(open(config_path, mode="r"))
    except:
        values = {}

    # Merge with values from CLI, preferring CLI
    try:
        values |= {k: v for k, v in kwargs.items() if v is not None}
    except:
        pass

    # Return all user-passed settings as dict
    return values


def get_value(
    key: str,
    cls: type[BaseSettings] = BaseSettings,
    new: bool = False,
    **values,
) -> dict[str,]:
    #
    if key in values:
        return {key: cls.get(key, **values)}

    #
    elif (cls is BaseSettings) or (not new):
        return {}

    #
    else:
        return {key: cls(**values)}
