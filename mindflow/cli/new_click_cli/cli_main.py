import click

# from mindflow.cli.new_click_cli.commands.config import config
from mindflow.cli.new_click_cli.commands.ask import ask
from mindflow.cli.new_click_cli.commands.delete import delete
from mindflow.cli.new_click_cli.commands.index import index
from mindflow.cli.new_click_cli.commands.inspect import inspect
from mindflow.cli.new_click_cli.commands.login import login
from mindflow.cli.new_click_cli.commands.query import query

@click.group()
def mindflow_cli():
    pass

mindflow_cli.add_command(login)
mindflow_cli.add_command(index)
mindflow_cli.add_command(query)
mindflow_cli.add_command(ask)
mindflow_cli.add_command(inspect)
mindflow_cli.add_command(delete)

if __name__ == '__main__':
    mindflow_cli()