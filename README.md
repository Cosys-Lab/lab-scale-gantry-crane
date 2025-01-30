# lab-scale-gantry-crane
Repository containing the files to create the lab-scale gantry crane used in a couple of publications.

## python modules

I usually structure my projectes in the following way:

/topic1
|-/module1
|--/__init__.py
|--/foo.py
|--/bar.py
|-/module2
|--/...
|-/src
|--/code-using-modules.py
/topic2
...

Usually code within a topic is self contained.

When running a python file the directory of that file is included in the path to look for modules, but the problem is that the modules are on the same level as the /src folder, so they aren't found.

You could run the scripts in source from the /topic1 folder with `python -m ./src/code-using-modules.py`, but that doesn't integrate well with the run button in vscode, as far as I can tell this always does "run current file in terminal".

The cleanest solution so far is to create `<somelibraries>.pth` files in the `{venv-root}/lib/{python-version}/site-packages` directory containing the path to the libraries, that adds those paths to the pythonpath of the virtual environment

In this case I made a `repomodules.pth` file with content

    C:\Users\Joost\Documents\git\rockit-tests\trajectory-generation
    C:\Users\Joost\Documents\git\rockit-tests\trinamic

Each of the topics containing modules should be such a directory.
Probably sth that I should script, but it's a setup once thing, so not too concerned about it.

Lastly, within the modules both absolute and relative imports can be used,
e.g. if `foo.py` imports `bar.py` both `import module1.bar` and `import .bar` work. 

See also:

https://stackoverflow.com/questions/4757178/how-do-you-set-your-pythonpath-in-an-already-created-virtualenv

and straight to the specific answer: https://stackoverflow.com/a/47184788