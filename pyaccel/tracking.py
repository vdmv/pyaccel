""" Pyaccel tracking module

This module concentrates all tracking routines of the accelerator.
Most of them take a structure called 'positions' as an argument which
should store the initial coordinates of the particle, or the bunch of particles
to be tracked. Most of these routines generate tracked particle positions as
output, among other data. These input and ouput particle positions are stored
as native python lists or numpy arrays. Depending on the routine these position
objects may have one, two, three or four indices. These indices are used to
select particle's inices (p), coordinates(c), lattice element indices(e) or
turn number (n). For example, v = pos[p,c,e,n]. Routines in these module may
return particle positions structure missing one or more indices but the
PCEN ordering is preserved.
"""

import numpy as _numpy
import trackcpp as _trackcpp
import pyaccel.accelerator as _accelerator
import pyaccel.utils as _utils


_interactive = _utils.interactive

lost_planes = (None, 'x', 'y', 'z')


class TrackingException(Exception):
    pass


@_interactive
def element_pass(element, particles, **kwargs):
    """Track particle(s) through an element.

    Accepts one or multiple particles initial positions. In the latter case,
    a list of particles or numpy 2D array (with particle as second index)
    should be given as input; also, outputs get an additional dimension,
    with particle as second index.

    Keyword arguments:
    element         -- 'Element' object
    particles       -- initial 6D particle(s) position(s)
                       ex.1: particles = [rx,px,ry,py,de,dl]
                       ex.2: particles = [[rx1,px1,ry1,py1,de1,dl1],
                                          [rx2,px2,ry2,py2,de2,dl2]]
                       ex.3: particles = numpy.array(
                                          [[rx1,px1,ry1,py1,de1,dl1],
                                           [rx2,px2,ry2,py2,de2,dl2]])
    energy          -- energy of the beam [eV]
    harmonic_number -- harmonic number of the lattice
    cavity_on       -- cavity on state (True/False)
    radiation_on    -- radiation on state (True/False)
    vchamber_on     -- vacuum chamber on state (True/False)

    Returns:
    particles_out   -- a numpy array with tracked 6D position(s) of the
                       particle(s). If elementpass is invoked for a single
                       particle then 'particles_out' is a simple vector with
                       one index that refers to the particle coordinates. If
                       'position' represents many particles, the first index of
                       'position_out' selects the particle and the second index
                       selects the coordinate.

    Raises TrackingException
    """

    # checks if all necessary arguments have been passed
    keys_needed = ['energy','harmonic_number','cavity_on','radiation_on','vchamber_on']
    for key in keys_needed:
        if key not in kwargs:
            raise TrackingException("missing '" + key + "' argument'")


    # creates accelerator for tracking
    accelerator = _accelerator.Accelerator(**kwargs)

    # checks whether single or multiple particles
    particles, return_ndarray, _ = _process_args(accelerator, particles)

    # tracks through the list of pos
    particles_out = _numpy.zeros(particles.shape)
    particles_out.fill(float('nan'))

    for i in range(particles.shape[0]):
        p_in = _Numpy2CppDoublePos(particles[i,:])
        if _trackcpp.track_elementpass_wrapper(element._e,p_in, accelerator._accelerator):
            raise TrackingException
        particles_out[i,:] = _CppDoublePos2Numpy(p_in)

    # returns tracking data
    if particles_out.shape[0] == 1 and not return_ndarray:
        particles_out = particles_out[0,:]

    return particles_out


@_interactive
def line_pass(accelerator, particles, indices=None, element_offset=0):
    """Track particle(s) along a line.

    Accepts one or multiple particles initial positions. In the latter case,
    a list of particles or a numpy 2D array (with particle as second index)
    should be given as input; tracked particles positions at the entrances of
    elements are output variables, as well as information on whether particles
    have been lost along the tracking and where they were lost.

    Keyword arguments: (accelerator, particles, indices, element_offset)

    accelerator -- Accelerator object
    particles   -- initial 6D particle(s) position(s).
                   Few examples
                        ex.1: particles = [rx,px,ry,py,de,dl]
                        ex.2: particles = [[0.001,0,0,0,0,0],[0.002,0,0,0,0,0]]
                        ex.3: particles = numpy.zeros((Np,6))
    indices     -- list of indices corresponding to accelerator elements at
                   whose entrances, tracked particles positions are to be
                   stored; string 'open' corresponds to selecting all elements.
    element_offset -- element offset (default 0) for tracking. tracking will
                      start at the element with index 'element_offset'

    Returns: (particles_out, lost_flag, lost_element, lost_plane)

    particles_out -- 6D position for each particle at entrance of each element.
                     The structure of 'particles_out' depends on inputs
                     'particles' and 'indices'. If 'indices' is None then only
                     tracked positions at the end of the line are returned.
                     There are still two possibilities for the structure of
                     particles_out, depending on 'particles':

                    (1) if 'particles' is a single particle defined as a python
                        list of coordinates, 'particles_out' will also be a
                        simple list:
                        ex.:particles = [rx1,px1,ry1,py1,de1,dl1]
                            indices = None
                            particles_out=numpy.array([rx2,px2,ry2,py2,de2,dl2])

                    (2) if 'particles' is either a python list of particles or a
                        numpy matrix then 'particles_out' will be a matrix
                        (numpy array of arrays) whose first index selects a
                        particular particle and second index picks a coordinate
                        rx, px, ry, py, de or dl, in this order.
                        ex.:particles = [[rx1,px1,ry1,py1,de1,dl1],
                                         [rx2,px2,ry2,py2,de2,dl2]]
                            indices = None
                            particles_out = numpy.array(
                                [ [rx3,px3,ry3,py3,de3,dl3],
                                  [rx4,px4,ry4,py4,de4,dl4]
                                ])

                    Now, if 'indices' is not None then 'particles_out' can be
                    either

                    (3) a numpy matrix, when 'particles' is a single particle
                        defined as a python list. The first index of
                        'particles_out' runs through the particle coordinate and
                        the second through the element index

                    (4) a numpy rank-3 tensor, when 'particles' is the initial
                        positions of many particles. The first index now is the
                        particle index, the second index is the coordinate index
                        and the third index is the element index at whose
                        entrances particles coordinates are returned.

    lost_flag    -- a general flag indicating whether there has been particle
                    loss.
    lost_element -- list of element index where each particle was lost
                    If the particle survived the tracking through the line its
                    corresponding element in this list is set to None. When
                    there is only one particle defined as a python list (not as
                    a numpy matrix with one column) 'lost_element' returns a
                    single number.
    lost_plane   -- list of strings representing on what plane each particle
                    was lost while being tracked. If the particle is not lost
                    then its corresponding element in the list is set to None.
                    If it is lost in the horizontal or vertical plane it is set
                    to string 'x' or 'y', correspondingly. If tracking is
                    performed with a single particle described as a python list
                    then 'lost_plane' returns a single string

    """

    # store only final position?
    args = _trackcpp.LinePassArgs()
    args.trajectory = False if indices is None else True

    # checks whether single or multiple particles, reformats particles
    particles, return_ndarray, indices = _process_args(accelerator, particles,
                                                       indices)

    # initialize particles_out tensor according to input options
    if indices is None:
        particles_out = _numpy.ones((particles.shape[0],6))
    else:
        particles_out = _numpy.zeros((particles.shape[0], 6, len(indices)))
    particles_out.fill(float('nan'))

    lost_flag = False
    lost_element, lost_plane = [], []

    # loop over particles
    for i in range(particles.shape[0]):

        # python particle pos -> trackcpp particle pos
        args.element_offset = element_offset
        p_in = _Numpy2CppDoublePos(particles[i,:])
        p_out = _trackcpp.CppDoublePosVector()

        # tracking
        if _trackcpp.track_linepass_wrapper(accelerator._accelerator,
                                            p_in, p_out, args):
            lost_flag = True

        # trackcpp particle pos -> python particle pos
        if indices is None:
            particles_out[i,:] = _CppDoublePos2Numpy(p_out[0])
        else:
            for j in range(len(indices)):
                particles_out[i,:,j] = _CppDoublePos2Numpy(p_out[indices[j]])

        # fills vectors with info about particle loss
        if args.lost_plane:
            lost_element.append(args.element_offset)
            lost_plane.append(lost_planes[args.lost_plane])
        else:
            lost_element.append(None)
            lost_plane.append(None)

    # simplifies output structure in case of single particle and python list
    if len(lost_element) == 1 and not return_ndarray:
        if len(particles_out.shape) == 3:
            particles_out = particles_out[0,:,:]
        else:
            particles_out = particles_out[0,:]
        lost_element = lost_element[0]
        lost_plane = lost_plane[0]

    return particles_out, lost_flag, lost_element, lost_plane


@_interactive
def ring_pass(accelerator, particles, nr_turns = 1,
             turn_by_turn = None, element_offset=0):
    """Track particle(s) along a ring.

    Accepts one or multiple particles initial positions. In the latter case,
    a list of particles or a numpy 2D array (with particle as firts index)
    should be given as input; tracked particles positions at the end of
    the ring are output variables, as well as information on whether particles
    have been lost along the tracking and where they were lost.

    Keyword arguments: (accelerator, particles, nr_turns,
                        turn_by_turn, elment_offset)

    accelerator    -- Accelerator object
    particles      -- initial 6D particle(s) position(s).
                      Few examples
                        ex.1: particles = [rx,px,ry,py,de,dl]
                        ex.2: particles = [[0.001,0,0,0,0,0],[0.002,0,0,0,0,0]]
                        ex.3: particles = numpy.zeros((Np,6))
    nr_turns       -- number of turns around ring to track each particle.
    turn_by_turn   -- parameter indicating what turn by turn positions are to
                      be returned. If None ringpass returns particles
                      positions only at the end of the ring, at the last turn.
                      If turn_by_turn is 'closed' ringpass returns positions
                      at the end of the ring for every turn. If it is 'open'
                      than positions are returned at the beginning of every
                      turn.

    element_offset -- element offset (default 0) for tracking. tracking will
                      start at the element with index 'element_offset'

    Returns: (particles_out, lost_flag, lost_turn, lost_element, lost_plane)

    particles_out -- 6D position for each particle at end of ring. The structure
                     of 'particles_out' depends on inputs 'particles' and
                     'turn_by_turn'. If 'turn_by_turn' is None then only
                     tracked positions at the end 'nr_turns' are returned. There
                     are still two possibilities for the structure of
                     particles_out, depending on 'particles':

                    (1) if 'particles' is a single particle defined as a python
                        list of coordinates, 'particles_out' will also be a
                        simple list:
                        ex.:particles = [rx1,px1,ry1,py1,de1,dl1]
                            turn_by_turn = False
                            particles_out=numpy.array([rx2,px2,ry2,py2,de2,dl2])

                    (2) if 'particles' is either a python list of particles or a
                        numpy matrix then 'particles_out' will be a matrix
                        (numpy array of arrays) whose first index selects the
                        coordinate rx, px, ry, py, de or dl, in this order, and
                        the second index selects a particular particle.
                        ex.: particles = [[rx1,px1,ry1,py1,de1,dl1],
                                          [rx2,px2,ry2,py2,de2,dl2]]
                             turn_by_turn = False
                             particles_out = numpy.array(
                                 [ [rx3,px3,ry3,py3,de3,dl3],
                                   [rx4,px4,ry4,py4,de4,dl4]
                                 ])

                     'turn_by_turn' can also be either 'close' or 'open'. In
                     either case 'particles_out' will have tracked positions at
                     the entrances of the elements. The difference is that for
                     'closed' it will have an additional tracked position at the
                     exit of the last element, thus closing the data, in case
                     the line is a ring. The format of 'particles_out' is ...

                    (3) a numpy matrix, when 'particles' is a single particle
                        defined as a python list. The first index of
                        'particles_out' runs through coordinates rx, px, ry, py,
                        de or dl and the second index runs through the turn
                        number

                    (4) a numpy rank-3 tensor, when 'particles' is the initial
                        positions of many particles. The first index now runs
                        through particles, the second through coordinates and
                        the third through turn number.

    lost_flag    -- a general flag indicating whether there has been particle
                    loss.
    lost_turn    -- list of turn index where each particle was lost.
    lost_element -- list of element index where each particle was lost
                    If the particle survived the tracking through the ring its
                    corresponding element in this list is set to None. When
                    there is only one particle defined as a python list (not as
                    a numpy matrix with one column) 'lost_element' returns a
                    single number.
    lost_plane   -- list of strings representing on what plane each particle
                    was lost while being tracked. If the particle is not lost
                    then its corresponding element in the list is set to None.
                    If it is lost in the horizontal or vertical plane it is set
                    to string 'x' or 'y', correspondingly. If tracking is
                    performed with a single particle described as a python list
                    then 'lost_plane' returns a single string

    """

    # checks whether single or multiple particles, reformats particles
    particles, return_ndarray, _ = _process_args(accelerator, particles,
                                                 indices=None)

    # initialize particles_out tensor according to input options
    if turn_by_turn:
        particles_out = _numpy.zeros((particles.shape[0],6,nr_turns))
    else:
        particles_out = _numpy.zeros((particles.shape[0],6))
    particles_out.fill(float('nan'))
    lost_flag = False
    lost_turn, lost_element, lost_plane = [], [], []

    # static parameters of ringpass
    args = _trackcpp.RingPassArgs()
    args.nr_turns = nr_turns
    args.trajectory = True if turn_by_turn else False

    # loop over particles
    for i in range(particles.shape[0]):

        # python particle pos -> trackcpp particle pos
        args.element_offset = element_offset
        p_in = _Numpy2CppDoublePos(particles[i,:])
        p_out = _trackcpp.CppDoublePosVector()

        # tracking
        if _trackcpp.track_ringpass_wrapper(accelerator._accelerator,
                                            p_in, p_out, args):
            lost_flag = True

        # trackcpp particle pos -> python particle pos
        if turn_by_turn:
            if turn_by_turn == 'closed':
                for n in range(nr_turns):
                    particles_out[i,:,n] = _CppDoublePos2Numpy(p_out[n])
            elif turn_by_turn == 'open':
                particles_out[i,:,0] = particles[i,:]
                for n in range(1,nr_turns):
                    particles_out[i,:,n] = _CppDoublePos2Numpy(p_out[n-1])

        else:
            particles_out[i,:] = _CppDoublePos2Numpy(p_out[0])

        # fills vectors with info about particle loss
        if args.lost_plane:
            lost_turn.append(args.lost_turn)
            lost_element.append(args.lost_element)
            lost_plane.append(lost_planes[args.lost_plane])
        else:
            lost_turn.append(None)
            lost_element.append(None)
            lost_plane.append(None)

    # simplifies output structure in case of single particle and python list
    if len(lost_element) == 1 and not return_ndarray:
        if len(particles_out.shape) == 3:
            particles_out = particles_out[0,:,:]
        else:
            particles_out = particles_out[0,:]
        lost_turn = lost_turn[0]
        lost_element = lost_element[0]
        lost_plane = lost_plane[0]

    return particles_out, lost_flag, lost_turn, lost_element, lost_plane


@_interactive
def set_4d_tracking(accelerator):
    accelerator.cavity_on = False
    accelerator.radiation_on = False


@_interactive
def set_6d_tracking(accelerator):
    accelerator.cavity_on = True
    accelerator.radiation_on = True


@_interactive
def find_orbit4(accelerator, energy_offset = 0, indices=None, fixed_point_guess=None):
    """Calculate 4D closed orbit of accelerator and return it.

    Accepts an optional list of indices of ring elements where closed orbit
    coordinates are to be returned. If this argument is not passed, closed orbit
    positions are returned at the start of the first element. In addition a guess
    fixed point at the entrance of the ring may be provided.

    Keyword arguments:
    accelerator : Accelerator object
    energy_offset : relative energy deviation from nominal energy
    indices : may be a (list,tuple, numpy.ndarray) of element indices where
              closed orbit data is to be returned or a string:
               'open'  : return the closed orbit at the entrance of all elements.
               'closed': besides all the points of 'open' also return the orbit
                         at the exit of the last element.
             If indices is None the closed orbit is returned only at the
             entrance of the first element.
    fixed_point_guess -- A 6D position where to start the search of the closed
                         orbit at the entrance of the first element. If not
                         provided the algorithm will start with zero orbit.

    Returns:
     orbit : 4D closed orbit at the entrance of the selected elements as a 2D
        numpy array with the 4 phase space variables in the first dimension and
        the indices of the elements in the second dimension.

    Raises TrackingException
    """

    if fixed_point_guess is None:
        fixed_point_guess = _trackcpp.CppDoublePos()
    else:
        fixed_point_guess = _4Numpy2CppDoublePos(fixed_point_guess)
    fixed_point_guess.de = energy_offset


    _closed_orbit = _trackcpp.CppDoublePosVector()
    r = _trackcpp.track_findorbit4(accelerator._accelerator, _closed_orbit, fixed_point_guess)
    if r > 0:
        raise TrackingException(_trackcpp.string_error_messages[r])

    if indices is None:
        closed_orbit = _CppDoublePos24Numpy(_closed_orbit[0])
    elif indices == 'open':
        closed_orbit = _numpy.zeros((len(accelerator),4))
        for i in range(len(accelerator)):
            closed_orbit[i] = _CppDoublePos24Numpy(_closed_orbit[i])
    elif indices =='closed':
        closed_orbit = _numpy.zeros((len(accelerator)+1,4))
        for i in range(len(accelerator)):
            closed_orbit[i] = _CppDoublePos24Numpy(_closed_orbit[i])
        closed_orbit[-1] = closed_orbit[0]
    elif isinstance(indices,(list,tuple,_numpy.ndarray)):
        closed_orbit = _numpy.zeros((len(indices),4))
        for i,ind in enumerate(indices):
            closed_orbit[i] = _CppDoublePos24Numpy(_closed_orbit[ind])
    else:
        raise TrackingException("invalid value for 'indices' in findorbit4")

    return closed_orbit.T


@_interactive
def find_orbit6(accelerator, indices=None, fixed_point_guess=None):
    """Calculate 6D closed orbit of accelerator and return it.

    Accepts an optional list of indices of ring elements where closed orbit
    coordinates are to be returned. If this argument is not passed, closed orbit
    positions are returned at the start of the first element. In addition a guess
    fixed point at the entrance of the ring may be provided.

    Keyword arguments:
    accelerator : Accelerator object
    indices : may be a (list,tuple, numpy.ndarray) of element indices where
              closed orbit data is to be returned or a string:
               'open'  : return the closed orbit at the entrance of all elements.
               'closed': besides all the points of 'open' also return the orbit
                         at the exit of the last element.
             If indices is None the closed orbit is returned only at the
             entrance of the first element.
    fixed_point_guess -- A 6D position where to start the search of the closed
                         orbit at the entrance of the first element. If not
                         provided the algorithm will start with zero orbit.

    Returns:
     orbit : 6D closed orbit at the entrance of the selected elements as a 2D
        numpy array with the 6 phase space variables in the first dimension and
        the indices of the elements in the second dimension.

    Raises TrackingException
    """
    if fixed_point_guess is None:
        fixed_point_guess = _trackcpp.CppDoublePos()
    else:
        fixed_point_guess = _Numpy2CppDoublePos(fixed_point_guess)


    _closed_orbit = _trackcpp.CppDoublePosVector()
    r = _trackcpp.track_findorbit6(accelerator._accelerator, _closed_orbit, fixed_point_guess)
    if r > 0:
        raise TrackingException(_trackcpp.string_error_messages[r])

    if indices is None:
        closed_orbit = _CppDoublePos2Numpy(_closed_orbit[0])[None,:]
    elif indices == 'open':
        closed_orbit = _numpy.zeros((len(accelerator),6))
        for i in range(len(accelerator)):
            closed_orbit[i] = _CppDoublePos2Numpy(_closed_orbit[i])
    elif indices =='closed':
        closed_orbit = _numpy.zeros((len(accelerator)+1,6))
        for i in range(len(accelerator)):
            closed_orbit[i] = _CppDoublePos2Numpy(_closed_orbit[i])
        closed_orbit[-1] = closed_orbit[0]
    elif isinstance(indices,(list,tuple,_numpy.ndarray)):
        closed_orbit = _numpy.zeros((len(indices),6))
        for i,ind in enumerate(indices):
            closed_orbit[i] = _CppDoublePos2Numpy(_closed_orbit[ind])
    else:
        raise TrackingException("invalid value for 'indices' in findorbit6")

    return closed_orbit.T


@_interactive
def find_m66(accelerator, indices=None, closed_orbit=None):
    """Calculate 6D transfer matrices of elements in an accelerator.

    Keyword arguments:
    accelerator
    indices
    closed_orbit

    Return values:
    m66
    cumul_trans_matrices -- values at the start of each lattice element
    """
    if indices is None:
        indices = list(range(len(accelerator)))

    if closed_orbit is None:
        # Closed orbit is calculated by trackcpp
        _closed_orbit = _trackcpp.CppDoublePosVector()
    else:
        _closed_orbit = _Numpy2CppDoublePosVector(closed_orbit)

    _cumul_trans_matrices = _trackcpp.CppMatrixVector()
    _m66 = _trackcpp.Matrix()
    _v0 = _trackcpp.CppDoublePos()
    r = _trackcpp.track_findm66(
        accelerator._accelerator,
        _closed_orbit,
        _cumul_trans_matrices,
        _m66,
        _v0
    )
    if r > 0:
        raise TrackingException(_trackcpp.string_error_messages[r])

    m66 = _CppMatrix2Numpy(_m66)
    if indices == 'm66':
        return m66

    cumul_trans_matrices = MatrixList(_cumul_trans_matrices)

    return m66, cumul_trans_matrices


@_interactive
def find_m44(accelerator, indices=None, energy_offset = 0.0, closed_orbit=None):
    """Calculate 4D transfer matrices of elements in an accelerator.

    Keyword arguments:
    accelerator
    indices
    energy_offset
    closed_orbit

    Return values:
    m44
    cumul_trans_matrices -- values at the start of each lattice element
    """
    if indices is None:
        indices = list(range(len(accelerator)))

    if closed_orbit is None:
        # calcs closed orbit if it was not passed.
        fixed_point_guess = _trackcpp.CppDoublePos()
        fixed_point_guess.de = energy_offset
        _closed_orbit = _trackcpp.CppDoublePosVector()
        r = _trackcpp.track_findorbit4(accelerator._accelerator, _closed_orbit, fixed_point_guess)
        if r > 0:
            raise TrackingException(_trackcpp.string_error_messages[r])
    else:
        _closed_orbit = _4Numpy2CppDoublePosVector(closed_orbit,de=energy_offset)

    _cumul_trans_matrices = _trackcpp.CppMatrixVector()
    _m44 = _trackcpp.Matrix()
    _v0 = _trackcpp.CppDoublePos()
    r = _trackcpp.track_findm66(
        accelerator._accelerator,
        _closed_orbit,
        _cumul_trans_matrices,
        _m44,
        _v0
    )
    if r > 0:
        raise TrackingException(_trackcpp.string_error_messages[r])

    m44 = _CppMatrix24Numpy(_m44)
    if indices == 'm44':
        return m44

    cumul_trans_matrices = []
    for i in range(len(_cumul_trans_matrices)):
        cumul_trans_matrices.append(_CppMatrix24Numpy(_cumul_trans_matrices[i]))

    return m44, cumul_trans_matrices


def _CppMatrix2Numpy(_m):
    m = _numpy.zeros((6,6))
    for r in range(6):
        for c in range(6):
            m[r,c] = _m[r][c]
    return m


def _CppMatrix24Numpy(_m):
    m = _numpy.zeros((4,4))
    for r in range(4):
        for c in range(4):
            m[r,c] = _m[r][c]
    return m


def _Numpy2CppDoublePos(p_in):
    p_out = _trackcpp.CppDoublePos()
    p_out.rx, p_out.px = float(p_in[0]), float(p_in[1])
    p_out.ry, p_out.py = float(p_in[2]), float(p_in[3])
    p_out.de, p_out.dl = float(p_in[4]), float(p_in[5])
    return p_out


def _4Numpy2CppDoublePos(p_in):
    p_out = _trackcpp.CppDoublePos()
    p_out.rx, p_out.px = float(p_in[0]), float(p_in[1])
    p_out.ry, p_out.py = float(p_in[2]), float(p_in[3])
    p_out.de, p_out.dl = 0,0
    return p_out


def _CppDoublePos2Numpy(p_in):
    return _numpy.array((p_in.rx,p_in.px,p_in.ry,p_in.py,p_in.de,p_in.dl))


def _CppDoublePos24Numpy(p_in):
    return _numpy.array((p_in.rx,p_in.px,p_in.ry,p_in.py))


def _CppDoublePosVector2Numpy(orbit, indices):
    if indices == 'closed' or indices == 'open':
        _indices = range(len(orbit))
    elif indices is None:
        _indices = [len(orbit)-1]
    elif isinstance(indices,int):
        _indices = [indices]

    orbit_out = _numpy.zeros((6, len(_indices)))
    for i in range(len(_indices)):
        orbit_out[:,i] = [
            orbit[_indices[i]].rx, orbit[_indices[i]].px,
            orbit[_indices[i]].ry, orbit[_indices[i]].py,
            orbit[_indices[i]].de, orbit[_indices[i]].dl
        ]
    if indices is None:
        return orbit_out[0,:]
    else:
        return orbit_out


def _Numpy2CppDoublePosVector(orbit):
    if isinstance(orbit, _trackcpp.CppDoublePosVector):
        return orbit
    if isinstance(orbit, _numpy.ndarray):
        orbit_out = _trackcpp.CppDoublePosVector()
        for i in range(orbit.shape[1]):
            orbit_out.push_back(_trackcpp.CppDoublePos(
                orbit[0,i], orbit[1,i],
                orbit[2,i], orbit[3,i],
                orbit[4,i], orbit[5,i]))
    elif isinstance(orbit, (list,tuple)):
        orbit_out = _trackcpp.CppDoublePosVector()
        orbit_out.push_back(_trackcpp.CppDoublePos(
            orbit[0], orbit[1],
            orbit[2], orbit[3],
            orbit[4], orbit[5]))
    else:
        raise TrackingException('invalid orbit argument')
    return orbit_out


def _4Numpy2CppDoublePosVector(orbit,de=0.0):
    if isinstance(orbit, _trackcpp.CppDoublePosVector):
        return orbit
    if isinstance(orbit, _numpy.ndarray):
        orbit_out = _trackcpp.CppDoublePosVector()
        for i in range(orbit.shape[1]):
            orbit_out.push_back(_trackcpp.CppDoublePos(
                orbit[0,i], orbit[1,i],
                orbit[2,i], orbit[3,i],
                de        , 0.0))
    elif isinstance(orbit, (list,tuple)):
        orbit_out = _trackcpp.CppDoublePosVector()
        orbit_out.push_back(_trackcpp.CppDoublePos(
            orbit[0], orbit[1],
            orbit[2], orbit[3],
            de      , 0.0))
    else:
        raise TrackingException('invalid orbit argument')
    return orbit_out


def _process_args(accelerator, pos, indices=None):

    # checks whether single or multiple particles
    return_ndarray = True
    if isinstance(pos, (list,tuple)):
        if isinstance(pos[0], (list,tuple)):
            pos = _numpy.array(pos)
        else:
            pos = _numpy.array(pos,ndmin=2)
            return_ndarray = False
    elif isinstance(pos, _numpy.ndarray):
        if len(pos.shape) == 1:
            pos = _numpy.array(pos,ndmin=2)
    if indices == 'open':
        indices = list(range(len(accelerator)))
    elif indices == 'closed':
        indices = list(range(len(accelerator)+1))

    return pos, return_ndarray, indices


def _print_CppDoublePos(pos):
    print('')
    print('{0:+.16f}'.format(pos.rx))
    print('{0:+.16f}'.format(pos.px))
    print('{0:+.16f}'.format(pos.ry))
    print('{0:+.16f}'.format(pos.py))
    print('{0:+.16f}'.format(pos.de))
    print('{0:+.16f}'.format(pos.dl))
    print('')


class MatrixList(object):

    def __init__(self, matrix_list=None):
        """Read-only list of matrices.

        Keyword argument:
        matrix_list -- trackcpp Matrix vector (default: None)
        """
        # TEST!
        if matrix_list is not None:
            if isinstance(matrix_list, _trackcpp.CppMatrixVector):
                self._ml = matrix_list
            else:
                raise TrackingException('invalid Matrix vector')
        else:
            self._ml = _trackcpp.CppMatrixVector()

    def __len__(self):
        return len(self._ml)

    def __getitem__(self, index):
        return _numpy.array(self._ml[index])

    def append(self, value):
        if isinstance(value, _trackcpp.Matrix):
            self._ml.append(value)
        elif isinstance(value, _numpy.ndarray):
            m = _trackcpp.Matrix()
            for line in value:
                line_as_floats = [float(x) for x in line]
                m.append(line_as_floats)
            self._ml.append(m)
        elif self._is_list_of_lists(value):
            m = _trackcpp.Matrix()
            for line in value:
                m.append(line)
            self._ml.append(m)
        else:
            raise TrackingException('can only append matrix-like objects')

    def _is_list_of_lists(self, value):
        valid_types = (list, tuple)

        if not isinstance(value, valid_types):
            return False

        for line in value:
            if not isinstance(line, valid_types):
                return False

        return True


# Legacy API
elementpass = _utils.deprecated(element_pass)
linepass = _utils.deprecated(line_pass)
ringpass = _utils.deprecated(ring_pass)
set4dtracking = _utils.deprecated(set_4d_tracking)
set6dtracking = _utils.deprecated(set_6d_tracking)
findorbit4 = _utils.deprecated(find_orbit4)
findorbit6 = _utils.deprecated(find_orbit6)
findm66 = _utils.deprecated(find_m66)
findm44 = _utils.deprecated(find_m44)
