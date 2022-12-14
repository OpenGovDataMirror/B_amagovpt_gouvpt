import os
import sys

from invoke import task, call


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__)))

LANGUAGES = ['pt']

I18N_ROOT = 'gouvpt/translations'
THEME_ROOT = os.path.join(ROOT, 'gouvpt')

I18N_DOMAIN = 'gouvpt'

CLEAN_PATTERNS = [
    'build', 'dist', '**/*.pyc', '**/*.mo', 'reports'
]


def color(code):
    '''A simple ANSI color wrapper factory'''
    return lambda t: '\033[{0}{1}\033[0;m'.format(code, t)


green = color('1;32m')
red = color('1;31m')
blue = color('1;30m')
cyan = color('1;36m')
purple = color('1;35m')
white = color('1;39m')


def header(text):
    '''Display an header'''
    print(' '.join((blue('>>'), cyan(text))))
    sys.stdout.flush()


def info(text, *args, **kwargs):
    '''Display informations'''
    text = text.format(*args, **kwargs)
    print(' '.join((purple('>>>'), text)))
    sys.stdout.flush()


def success(text):
    '''Display a success message'''
    print(' '.join((green('✔'), white(text))))
    sys.stdout.flush()


def error(text):
    '''Display an error message'''
    print(red('✘ {0}'.format(text)))
    sys.stdout.flush()


def exit(text=None, code=-1):
    if text:
        error(text)
    sys.exit(-1)


@task
def clean(ctx):
    '''Cleanup all build artifacts'''
    header(clean.__doc__)
    with ctx.cd(ROOT):
        for pattern in CLEAN_PATTERNS:
            info(pattern)
            ctx.run('rm -rf {0}'.format(' '.join(CLEAN_PATTERNS)))


@task
def test(ctx, report=False, verbose=False):
    '''Run tests suite'''
    header(test.__doc__)
    cmd = ['pytest']
    if verbose:
        cmd.append('-v')
    if report:
        cmd.append('--junitxml=reports/tests.xml')
    with ctx.cd(ROOT):
        ctx.run(' '.join(cmd), pty=True)


@task
def cover(ctx, report=False, verbose=False):
    '''Run tests suite with coverage'''
    header(cover.__doc__)
    cmd = [
        'pytest',
        '--cov-config coverage.rc',
        '--cov-report term',
        '--cov=gouvpt',
    ]
    if verbose:
        cmd.append('-v')
    if report:
        cmd += [
            '--cov-report html:reports/coverage',
            '--cov-report xml:reports/coverage.xml',
            '--junitxml=reports/tests.xml'
        ]
    with ctx.cd(ROOT):
        ctx.run(' '.join(cmd), pty=True)


@task
def qa(ctx):
    '''Run a quality report'''
    header(qa.__doc__)
    with ctx.cd(ROOT):
        info('Python Static Analysis')
        flake8_results = ctx.run('flake8 gouvpt tests', pty=True, warn=True)
        if flake8_results.failed:
            error('There is some lints to fix')
        else:
            success('No lint to fix')
        info('Ensure PyPI can render README and CHANGELOG')
        readme_results = ctx.run('python setup.py check -r -s', pty=True, warn=True, hide=True)
        if readme_results.failed:
            print(readme_results.stdout)
            error('README and/or CHANGELOG is not renderable by PyPI')
        else:
            success('README and CHANGELOG are renderable by PyPI')
    if flake8_results.failed or readme_results.failed:
        exit('Quality check failed', flake8_results.return_code or readme_results.return_code)
    success('Quality check OK')


@task
def i18n(ctx):
    '''Extract translatable strings'''
    header(i18n.__doc__)
    with ctx.cd(ROOT):
        ctx.run('mkdir -p {}'.format(I18N_ROOT))
        ctx.run('python setup.py extract_messages')
        for lang in LANGUAGES:
            pofile = os.path.join(I18N_ROOT, lang, 'LC_MESSAGES', '{}.po'.format(I18N_DOMAIN))
            if not os.path.exists(pofile):
                ctx.run('python setup.py init_catalog -l {}'.format(lang))
            else:
                ctx.run('python setup.py update_catalog -l {}'.format(lang))
    success('Updated translations')


@task
def i18nc(ctx):
    '''Compile translations'''
    header(i18nc.__doc__)
    # Plugin translations (harvesters, views...)
    info('Compile plugin translations')
    with ctx.cd(ROOT):
        ctx.run('python setup.py compile_catalog')

    # Theme translations
    info('Compile theme translations')
    with ctx.cd(THEME_ROOT):
        ctx.run('pybabel compile -D {0} -d translations --statistics'.format(I18N_DOMAIN))


@task
def assets_watch(ctx):
    '''Build assets on change'''
    header(assets_watch.__doc__)
    with ctx.cd(ROOT):
        ctx.run('npm run dev', pty=True)


@task
def assets_build(ctx):
    '''Build static assets'''
    header(assets_build.__doc__)
    with ctx.cd(ROOT):
        ctx.run('npm run build', pty=True)


@task(i18nc, assets_build)
def dist(ctx, buildno=None):
    '''Package for distribution'''
    header(dist.__doc__)
    perform_dist(ctx, buildno)


@task(i18nc)
def pydist(ctx, buildno=None):
    '''Perform python packaging (without compiling assets)'''
    header(pydist.__doc__)
    perform_dist(ctx, buildno)


def perform_dist(ctx, buildno=None):
    cmd = ['python setup.py']
    if buildno:
        cmd.append('egg_info -b {0}'.format(buildno))
    cmd.append('bdist_wheel')
    with ctx.cd(ROOT):
        ctx.run(' '.join(cmd), pty=True)
    success('Distribution is available in dist directory')


@task(clean, qa, call(cover, report=True), dist, default=True)
def all(ctx):
    '''Run tests, reports and packaging'''
    pass
