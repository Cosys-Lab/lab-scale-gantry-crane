def test_read_trajectory():
    trajectory = read_trajectory('path/to/trajectory/file')
    assert trajectory is not None

def test_write_trajectory():
    trajectory = create_sample_trajectory()
    write_trajectory('path/to/output/file', trajectory)
    assert os.path.exists('path/to/output/file')