# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import pytest
import aiohttp
import asyncio
import os
import stat
from tests.utils import asyncio_patch


from unittest.mock import patch, MagicMock
from gns3server.modules.iou.iou_vm import IOUVM
from gns3server.modules.iou.iou_error import IOUError
from gns3server.modules.iou import IOU


@pytest.fixture(scope="module")
def manager(port_manager):
    m = IOU.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def vm(project, manager, tmpdir, fake_iou_bin):
    fake_file = str(tmpdir / "iourc")
    with open(fake_file, "w+") as f:
        f.write("1")

    vm = IOUVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    config = manager.config.get_section_config("IOU")
    config["iouyap_path"] = fake_file
    manager.config.set_section_config("IOU", config)

    vm.iou_path = fake_iou_bin
    vm.iourc = fake_file
    return vm


@pytest.fixture
def fake_iou_bin(tmpdir):
    """Create a fake IOU image on disk"""

    path = str(tmpdir / "iou.bin")
    with open(path, "w+") as f:
        f.write('\x7fELF\x01\x01\x01')
    os.chmod(path, stat.S_IREAD | stat.S_IEXEC)
    return path


def test_vm(project, manager):
    vm = IOUVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    assert vm.name == "test"
    assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"


@patch("gns3server.config.Config.get_section_config", return_value={"iouyap_path": "/bin/test_fake"})
def test_vm_invalid_iouyap_path(project, manager, loop):
    with pytest.raises(IOUError):
        vm = IOUVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0e", project, manager)
        loop.run_until_complete(asyncio.async(vm.start()))


def test_start(loop, vm):
    with asyncio_patch("gns3server.modules.iou.iou_vm.IOUVM._check_requirements", return_value=True):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
            loop.run_until_complete(asyncio.async(vm.start()))
            assert vm.is_running()


def test_stop(loop, vm):
    process = MagicMock()

    # Wait process kill success
    future = asyncio.Future()
    future.set_result(True)
    process.wait.return_value = future

    with asyncio_patch("gns3server.modules.iou.iou_vm.IOUVM._check_requirements", return_value=True):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
            loop.run_until_complete(asyncio.async(vm.start()))
            assert vm.is_running()
            loop.run_until_complete(asyncio.async(vm.stop()))
            assert vm.is_running() is False
            process.terminate.assert_called_with()


def test_reload(loop, vm, fake_iou_bin):
    process = MagicMock()

    # Wait process kill success
    future = asyncio.Future()
    future.set_result(True)
    process.wait.return_value = future

    with asyncio_patch("gns3server.modules.iou.iou_vm.IOUVM._check_requirements", return_value=True):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
            loop.run_until_complete(asyncio.async(vm.start()))
            assert vm.is_running()
            loop.run_until_complete(asyncio.async(vm.reload()))
            assert vm.is_running() is True
            process.terminate.assert_called_with()


def test_close(vm, port_manager):
    with asyncio_patch("gns3server.modules.iou.iou_vm.IOUVM._check_requirements", return_value=True):
        with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
            vm.start()
            port = vm.console
            vm.close()
            # Raise an exception if the port is not free
            port_manager.reserve_console_port(port)
            assert vm.is_running() is False


def test_iou_path(vm, fake_iou_bin):

    vm.iou_path = fake_iou_bin
    assert vm.iou_path == fake_iou_bin


def test_path_invalid_bin(vm, tmpdir):

    iou_path = str(tmpdir / "test.bin")
    with pytest.raises(IOUError):
        vm.iou_path = iou_path

    with open(iou_path, "w+") as f:
        f.write("BUG")

    with pytest.raises(IOUError):
        vm.iou_path = iou_path


def test_create_netmap_config(vm):

    vm._create_netmap_config()
    netmap_path = os.path.join(vm.working_dir, "NETMAP")

    with open(netmap_path) as f:
        content = f.read()

    assert "513:0/0    1:0/0" in content
    assert "513:15/3    1:15/3" in content


def test_build_command(vm):

    assert vm._build_command() == [vm.iou_path, '-L', str(vm.application_id)]
