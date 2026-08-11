from mediadownloader.utils.paths import asset_path, project_root


def test_development_paths_point_to_project():
    assert (project_root() / "pyproject.toml").exists()
    assert asset_path("app.svg").exists()

