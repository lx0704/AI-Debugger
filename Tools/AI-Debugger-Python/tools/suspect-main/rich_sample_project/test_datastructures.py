from datastructures import Stack, Queue


def test_stack_push_pop_peek():
    s = Stack[int]()
    s.push(1); s.push(2)
    assert s.peek() == 2
    assert s.pop() == 2
    assert s.pop() == 1


def test_queue_enqueue_dequeue():
    q = Queue[str]()
    q.enqueue('a'); q.enqueue('b')
    assert list(q) == ['a', 'b']
    assert q.dequeue() == 'a'
    assert q.dequeue() == 'b'
