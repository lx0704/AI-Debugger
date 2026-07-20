from graphs import bfs, dijkstra


def test_bfs_order():
    adj = {
        'A': ['B', 'C'],
        'B': ['D'],
        'C': ['E'],
        'D': [],
        'E': []
    }
    order = bfs(adj, 'A')
    # BFS should visit level by level
    assert order[0] == 'A'
    assert set(order[1:3]) == {'B', 'C'}


def test_dijkstra_distances():
    adj = {
        'A': [('B', 1), ('C', 4)],
        'B': [('C', 2), ('D', 5)],
        'C': [('D', 1)],
        'D': []
    }
    dist = dijkstra(adj, 'A')
    assert dist['A'] == 0
    assert dist['B'] == 1
    assert dist['C'] == 3
    assert dist['D'] == 4
