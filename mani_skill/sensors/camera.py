from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence, Union

import numpy as np
import sapien
import sapien.render

from mani_skill.utils.structs import Actor, Articulation, Link
from mani_skill.utils.structs.pose import Pose
from mani_skill.utils.structs.types import Array

if TYPE_CHECKING:
    from mani_skill.envs.scene import ManiSkillScene

from mani_skill.utils import sapien_utils

from .base_sensor import BaseSensor, BaseSensorConfig


@dataclass
class CameraConfig(BaseSensorConfig):

    uid: str
    """uid (str): unique id of the camera"""
    pose: Pose
    """Pose of the camera"""
    width: int
    """width (int): width of the camera"""
    height: int
    """height (int): height of the camera"""
    fov: float = None
    """The field of view of the camera. Either fov or intrinsic must be given"""
    near: float = 0.01
    """near (float): near plane of the camera"""
    far: float = 100
    """far (float): far plane of the camera"""
    intrinsic: Array = None
    """intrinsics matrix of the camera. Either fov or intrinsic must be given"""
    entity_uid: str = None
    """entity_uid (str, optional): unique id of the entity to mount the camera. Defaults to None."""
    mount: Union[Actor, Link] = None
    """the Actor or Link to mount the camera on top of. This means the global pose of the mounted camera is now mount.pose * local_pose"""
    hide_link: bool = False
    """hide_link (bool, optional): whether to hide the link to mount the camera. Defaults to False."""
    texture_names: Sequence[str] = ("Color", "PositionSegmentation")
    """texture_names (Sequence[str], optional): texture names to render. Defaults to ("Color", "PositionSegmentation"). Note that the renderign speed will not really change if you remove PositionSegmentation"""

    def __post_init__(self):
        self.pose = Pose.create(self.pose)

    def __repr__(self) -> str:
        return self.__class__.__name__ + "(" + str(self.__dict__) + ")"


def parse_camera_cfgs(camera_cfgs):
    if isinstance(camera_cfgs, (tuple, list)):
        return dict([(cfg.uid, cfg) for cfg in camera_cfgs])
    elif isinstance(camera_cfgs, dict):
        return dict(camera_cfgs)
    elif isinstance(camera_cfgs, CameraConfig):
        return dict([(camera_cfgs.uid, camera_cfgs)])
    else:
        raise TypeError(type(camera_cfgs))


class Camera(BaseSensor):
    """Implementation of the Camera sensor which uses the sapien Camera."""

    def __init__(
        self,
        camera_cfg: CameraConfig,
        scene: ManiSkillScene,
        articulation: Articulation = None,
    ):
        super().__init__(cfg=camera_cfg)

        self.camera_cfg = camera_cfg

        entity_uid = camera_cfg.entity_uid
        if camera_cfg.mount is not None:
            self.entity = camera_cfg.mount
        elif entity_uid is None:
            self.entity = None
        else:
            if articulation is None:
                pass
            else:
                # if given an articulation and entity_uid (as a string), find the correct link to mount on
                # this is just for convenience so robot configurations can pick link to mount to by string/id
                self.entity = sapien_utils.get_obj_by_name(
                    articulation.get_links(), entity_uid
                )
            if self.entity is None:
                raise RuntimeError(f"Mount entity ({entity_uid}) is not found")

        intrinsic = camera_cfg.intrinsic
        assert (camera_cfg.fov is None and intrinsic is not None) or (
            camera_cfg.fov is not None and intrinsic is None
        )

        # Add camera to scene. Add mounted one if a entity is given
        if self.entity is None:
            self.camera = scene.add_camera(
                name=camera_cfg.uid,
                pose=camera_cfg.pose,
                width=camera_cfg.width,
                height=camera_cfg.height,
                fovy=camera_cfg.fov,
                intrinsic=intrinsic,
                near=camera_cfg.near,
                far=camera_cfg.far,
            )
        else:
            self.camera = scene.add_camera(
                name=camera_cfg.uid,
                mount=self.entity,
                pose=camera_cfg.pose,
                width=camera_cfg.width,
                height=camera_cfg.height,
                fovy=camera_cfg.fov,
                intrinsic=intrinsic,
                near=camera_cfg.near,
                far=camera_cfg.far,
            )

        if camera_cfg.hide_link:
            # TODO (stao): re-implement this
            from mani_skill import logger

            logger.warn(
                "camera hide_link option is not implemented yet so this won't be hidden"
            )

        # Filter texture names according to renderer type if necessary (legacy for Kuafu)
        self.texture_names = camera_cfg.texture_names

    def capture(self):
        self.camera.take_picture()

    def get_obs(self):
        images = {}
        for name in self.texture_names:
            image = self.get_picture(name)
            images[name] = image
        return images

    def get_picture(self, name: str):
        return self.camera.get_picture(name)

    # TODO (stao): Computing camera parameters on GPU sim is not that fast, especially with mounted cameras and for model_matrix computation.
    def get_params(self):
        return dict(
            extrinsic_cv=self.camera.get_extrinsic_matrix(),
            cam2world_gl=self.camera.get_model_matrix(),
            intrinsic_cv=self.camera.get_intrinsic_matrix(),
        )
