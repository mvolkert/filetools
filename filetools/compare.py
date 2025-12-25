# https://www.pyimagesearch.com/2014/09/15/python-compare-two-images/

# import the necessary packages
import numpy as np
import cv2
import os
try:
    from skimage.metrics import structural_similarity
    has_skimage = True
except ImportError:
    has_skimage = False

__all__ = ["are_similar"]


def is_blurry(filename: str, threshold=100):
    image = read_picture(filename)
    if image is None:
        return False
    return variance_of_laplacian(image) < threshold


def are_similar(filenameA: str, filenameB: str, threshold=0.9):
    if not has_skimage:
        yield "no skimage installed"
    imageA = read_picture(filenameA, 20)
    imageB = read_picture(filenameB, 20)
    if imageA is None or imageB is None:
        return False
    s = structural_similarity(imageA, imageB)
    if threshold < s:
        print(filenameA[0], filenameB[0], s)
    return threshold < s


def variance_of_laplacian(image):
    # compute the Laplacian of the image and then return the focus
    # measure, which is simply the variance of the Laplacian
    # the lower the more blurry, example threshold=100
    return cv2.Laplacian(image, cv2.CV_64F).var()


def mse(imageA, imageB):
    # the 'Mean Squared Error' between the two images is the
    # sum of the squared difference between the two images;
    # NOTE: the two images must have the same dimension
    err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
    err /= float(imageA.shape[0] * imageA.shape[1])

    # return the MSE, the lower the error, the more "similar"
    # the two images are
    return err


def compare_images(directory, nameA, nameB):
    if not has_skimage:
        yield "no skimage installed"
    # compute the mean squared error and structural similarity
    # index for the images
    imageA = read_picture(directory + "\\" + nameA)
    imageB = read_picture(directory + "\\" + nameB)
    m = mse(imageA, imageB)
    s = structural_similarity(imageA, imageB)
    print("m:", m)
    print("s", s)


def read_picture(path: tuple, xscale=500):
    fullname = os.path.join(*path)
    with open(fullname, 'rb') as img_stream:
        file_bytes = np.asarray(bytearray(img_stream.read()), dtype=np.uint8)
        picture = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
    if picture is None:
        print("failed to load", fullname)
        return
    if not picture.data:
        print("failed to load (data)", fullname)
        return
    picture = cv2.resize(picture, (xscale, xscale))
    # convert the images to grayscale
    picture = cv2.cvtColor(picture, cv2.COLOR_BGR2GRAY)
    return picture
