from bake import *

@task()
@parameter('out', 'boolean', default=False)
def runtests(task, runtime):
    try:
        import coverage
    except ImportError:
        coverage = None

    cmdline = ['nosetests']
    if task['out']:
        cmdline.append('-s')
    if coverage:
        cmdline.extend(['--with-coverage', '--cover-html', '--cover-erase',
            '--cover-package=mesh'])

    runtime.shell(cmdline, passthrough=True)
