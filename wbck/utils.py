import os


def zipdir(path, ziph, ignore_files=[]):
    for root, dirs, files in os.walk(path):
        for file in files:
            if file in ignore_files:
                continue
            ziph.write(
                os.path.join(root, file),
                os.path.relpath(
                    os.path.join(root, file),
                    os.path.join(path, '..')
                )
            )
