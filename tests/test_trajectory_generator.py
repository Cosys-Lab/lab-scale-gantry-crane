def test_trajectory_generation():
    assert trajectory_generator.generate_trajectory(0, 0, 0) == expected_trajectory_1
    assert trajectory_generator.generate_trajectory(1, 1, 1) == expected_trajectory_2
    assert trajectory_generator.generate_trajectory(-1, -1, -1) == expected_trajectory_3

def test_edge_case_trajectory_generation():
    assert trajectory_generator.generate_trajectory(float('inf'), float('inf'), float('inf')) == expected_trajectory_inf
    assert trajectory_generator.generate_trajectory(float('-inf'), float('-inf'), float('-inf')) == expected_trajectory_neg_inf
    assert trajectory_generator.generate_trajectory(0, 0, float('nan')) == expected_trajectory_nan