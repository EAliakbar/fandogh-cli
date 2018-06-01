#!/usr/bin/env python
import click

from .base_commands import FandoghCommand
from .utils import login_required, format_text, TextStyle
from .presenter import present
from .config import *
from .fandogh_client import *
from time import sleep
from .workspace import Workspace


@click.group("image")
def image():
    """
    Image management commands
    """
    pass


@click.command("init", cls=FandoghCommand)
@click.option('--name', prompt='image name', help='your image name')
@login_required
def init(name):
    """
    Upload project on the server
    """
    token = get_user_config().get('token')
    try:
        response = create_image(name, token)
    except FandoghBadRequest as exp:
        if name in {x['name'] for x in get_images(token)}:
            click.echo(
                format_text("You already have an image named '{}', "
                            "choose another name if this is not the same workspace".format(name), TextStyle.WARNING)
            )
        else:
            raise
    except Exception:
        raise
    else:
        click.echo(response)

    get_project_config().set('image.name', name)


@click.command('list', cls=FandoghCommand)
@login_required
def list_images():
    """
    List images
    """
    token = get_user_config().get('token')
    table = present(lambda: get_images(token),
                    renderer='table',
                    headers=['Name', 'Creation Date'],
                    columns=['name', 'created_at'])

    click.echo(table)


def show_image_logs(image_name, version):
    token = get_user_config().get('token')
    if not image_name:
        image_name = get_project_config().get('image.name')
    while True:
        response = get_image_build(image_name, version, token)
        click.clear()
        click.echo(response.get('logs'))
        if response.get('state') != 'BUILDING':
            break
        sleep(1)


@click.command('logs', cls=FandoghCommand)
@click.option('-i', '--image', 'image', help='The image name', default=None)
@click.option('--version', '-v', prompt='image version', help='your image version')
@login_required
def logs(image, version):
    """
    Display image log
    """
    show_image_logs(image, version)


@click.command("publish", cls=FandoghCommand)
@click.option('--version', '-v', prompt='Image version', help='your image version')
@click.option('-d', 'detach', is_flag=True, default=False,
              help='detach terminal, by default the image build logs will be shown synchronously.')
def publish(version, detach):
    """
    Publish new version of image
    """
    token = get_user_config().get('token')
    image_name = get_project_config().get('image.name')
    workspace = Workspace()
    if workspace.zip_file_size > max_workspace_size:
        click.echo(format_text(
            "The workspace size should not be larger than {}MB, its {}MB.".format(max_workspace_size,
                                                                                  round(workspace.zip_file_size, 2)),
            TextStyle.WARNING
        ))
        if not workspace.has_docker_ignore:
            click.echo(format_text(
                "[perhaps you may be able to take advantage of '.dockerignore' "
                "to reduce your worksspace size, check documentation for .dockerignore at: "
                "https://docs.docker.com/engine/reference/builder/#dockerignore-file]", TextStyle.BOLD
            ))

    bar = click.progressbar(length=int(workspace.zip_file_size_kb), label='Uploading the workspace')
    diff = 0

    def monitor_callback(monitor):
        nonlocal diff
        progress = monitor.bytes_read - diff
        bar.update(progress)
        diff += progress

    try:
        response = create_version(image_name, version, str(workspace), monitor_callback, token)
        bar.render_finish()
        click.echo(response)
    finally:
        workspace.clean()
    if detach:
        return
    else:
        show_image_logs(image_name, version)


@click.command("versions", cls=FandoghCommand)
@click.option('--image', help='The image name', default=None)
def versions(image):
    """
    List published versions of this image
    """
    token = get_user_config().get('token')
    if not image:
        image = get_project_config().get('image.name')
    table = present(lambda: list_versions(image, token),
                    renderer='table',
                    headers=['version', 'state'],
                    columns=['version', 'state'])
    if len(table.strip()):
        click.echo(table)
    else:
        click.echo("There is no version available for '{}'".format(image))


image.add_command(init)
image.add_command(publish)
image.add_command(versions)
image.add_command(list_images)
image.add_command(logs)