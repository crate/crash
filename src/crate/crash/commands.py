import functools
import glob


class Command(object):
    def complete(self, text):
        return []

    def __call__(self, cmd, *args, **kwargs):
        pass


def noargs_command(func):
    @functools.wraps(func)
    def wrapper(self, cmd, *args, **kwargs):
        if len(args):
            cmd.logger.critical('Command does not take any arguments.')
            return
        return func(self, cmd, *args, **kwargs)
    return wrapper


class HelpCommand(Command):
    """ print this help """

    @noargs_command
    def __call__(self, cmd, *args, **kwargs):
        out = []
        for k, v in sorted(cmd.commands.items()):
            doc = v.__doc__ and v.__doc__.strip()
            out.append('\{0:<30} {1}'.format(k, doc))
        return '\n'.join(out)


class ReadFileCommand(Command):
    """ read and execute statements from a file """
    def complete(self, text):
        text = text.lstrip(r'\r ')
        if text.endswith('.sql'):
            return []
        return glob.glob(text + '*.sql')

    def __call__(self, cmd, filename, *args, **kwargs):
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                cmd.process(line)


built_in_commands = {
    '?': HelpCommand(),
    'r': ReadFileCommand(),
}
