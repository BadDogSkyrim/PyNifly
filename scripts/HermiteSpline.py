def HermiteSpline(x, v1, b1, f1, v2, b2, f2):
    """
    Calculate a hermite spline == a quadratic interpolation in a nif.

    Follows nifskope's code at https://github.com/niftools/nifskope/blob/3a85ac55e65cc60abc3434cc4aaca2a5cc712eef/src/gl/glcontroller.cpp#L403

    """
    t1 = b1
    t2 = f2
    x2 = x*x
    x3 = x*x*x
    value = v1 * (2.0 * x3 - 3.0 * x2 + 1.0) + v2 * (-2.0 * x3 + 3.0 * x2) + t1 * (x3 - 2.0 * x2 + x) + t2 * (x3 - x2)
    return value

def ShowValue(x, v1, b1, f1, v2, b2, f2):
    print(f"{x} [{v1}, {b1}, {f1}] [{v2}, {b2}, {f2}] = {HermiteSpline(x, v1, b1, f1, v2, b2, f2)}")

for i in range(0, 11):
    ShowValue(i/10, 1, 0, 0, 1, 0, -1)