from math import atan2, cos, radians, sin, sqrt


def distance_m(lat1, lon1, lat2, lon2):
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 6371000 * 2 * atan2(sqrt(min(1, max(0, a))), sqrt(max(0, 1 - a)))


def inside(point, fence):
    return distance_m(point.lat, point.lon, fence.lat, fence.lon) <= fence.radius_m
