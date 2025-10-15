from collections import defaultdict
import heapq
import math

ASTAR_PATHS = 1
ASTAR_COST = 2
ASTAR_GOAL = 4


def astar(
    start,
    is_goal,
    neighbours,
    distance,
    heuristic=lambda p: 0,
    ret=ASTAR_COST | ASTAR_PATHS,
):
    """
    A-star pathfinding
        start: point
        is_goal(p) => bool
        neighbour(p) => [...points]
        distance(a, b) => number
        heuristic(p) => number
        ret: defines what astar should return

    Returns path [...points] and cost
    """

    frontier = []
    heapq.heappush(frontier, (0, start))

    preds = {}

    costs = defaultdict(lambda: math.inf)
    costs[start] = 0

    def build_retval(point):
        output = []
        if ret & ASTAR_PATHS:
            output.append(build_path(point))
        if ret & ASTAR_COST:
            output.append(costs[point])
        if ret & ASTAR_GOAL:
            output.append(point)
        return output

    def build_path(point):
        cur = point
        path = [point]
        while cur in preds:
            cur = preds[cur]
            path = [cur, *path]
        return path

    while frontier:
        _, cur = heapq.heappop(frontier)

        if is_goal(cur):
            return build_retval(cur)

        for neighbour in neighbours(cur):
            tcost = costs[cur] + distance(cur, neighbour)
            if tcost < costs[neighbour]:
                preds[neighbour] = cur
                costs[neighbour] = tcost
                priority = tcost + heuristic(neighbour)
                heapq.heappush(frontier, (priority, neighbour))

    return None
