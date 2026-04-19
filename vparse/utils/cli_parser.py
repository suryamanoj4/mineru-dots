import click


def arg_parse(ctx: 'click.Context') -> dict:
    # Parse extra arguments
    extra_kwargs = {}
    i = 0
    while i < len(ctx.args):
        arg = ctx.args[i]
        if arg.startswith('--'):
            param_name = arg[2:].replace('-', '_')  # Convert argument name format
            i += 1
            if i < len(ctx.args) and not ctx.args[i].startswith('--'):
                # Argument has a value
                try:
                    # Try converting to appropriate type
                    if ctx.args[i].lower() == 'true':
                        extra_kwargs[param_name] = True
                    elif ctx.args[i].lower() == 'false':
                        extra_kwargs[param_name] = False
                    elif '.' in ctx.args[i]:
                        try:
                            extra_kwargs[param_name] = float(ctx.args[i])
                        except ValueError:
                            extra_kwargs[param_name] = ctx.args[i]
                    else:
                        try:
                            extra_kwargs[param_name] = int(ctx.args[i])
                        except ValueError:
                            extra_kwargs[param_name] = ctx.args[i]
                except:
                    extra_kwargs[param_name] = ctx.args[i]
            else:
                # Boolean flag parameter
                extra_kwargs[param_name] = True
                i -= 1
        i += 1
    return extra_kwargs