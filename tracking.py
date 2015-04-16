import numpy as _numpy
import trackcpp as _trackcpp
import pyaccel.accelerator as _accelerator
from pyaccel.utils import interactive as _interactive


lost_planes = (None, 'x', 'y', 'z')


class TrackingException(Exception):
    pass


@_interactive
def elementpass(element, particles, **kwargs):

    """Track particle(s) through an element.

    Accepts one or multiple particles initial positions. In the latter case,
    a list of particles or numpy 2D array (with particle as second index)
    should be given as input; also, outputs get an additional dimension,
    with particle as second index.

    Keyword arguments:
    element         -- 'Element' object
    particles       -- initial 6D position or list of positions
    energy          -- energy of the beam [eV]
    harmonic_number -- harmonic number of the lattice
    cavity_on       -- cavity on state (True/False)
    radiation_on    -- radiation on state (True/False)
    vchamber_on     -- vacuum chamber on state (True/False)

    Returns:
    particles_out   -- a numpy array with tracked 6D position(s) of the
                       particle(s)

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

    for i in range(particles.shape[1]):
        p_in = _Numpy2CppDoublePos(particles[:,i])
        if _trackcpp.track_elementpass_wrapper(element._e,p_in, accelerator._accelerator):
            raise TrackingException
        particles_out[:,i] = \
            (p_in.rx, p_in.px, p_in.ry, p_in.py, p_in.de, p_in.dl)

    # returns tracking data
    if particles_out.shape[1] == 1 and not return_ndarray:
        particles_out = particles_out[:,0]

    return particles_out


@_interactive
def linepass(accelerator, particles, indices=None, element_offset=0):
    """Track particle(s) along a line.

    Accepts one or multiple particles initial positions. In the latter case,
    a list of particles or a numpy 2D array (with particle as second index)
    should be given as input; tracked particles positions along at the exits of
    elements are output variables, as well as information on whether particles
    have been lost along the tracking and where they were lost.

    Keyword arguments: (accelerator, particles, indices, element_offset)

    accelerator -- Accelerator object
    particles   -- initial 6D particle(s) position(s).
                   Few examples
                        ex.1: particles = [rx,px,ry,py,de,dl]
                        ex.2: particles = [[0.001,0,0,0,0,0],[0.002,0,0,0,0,0]]
                        ex.3: particles = numpy.zeros((6,Np))
    indices     -- list of indices corresponding to accelerator elements at
                   whose exits, tracked particles positions are to be
                   stored; string 'all' corresponds to selecting all elements.
    element_offset -- element offset (default 0) for tracking. tracking will
                      start at the element with index 'element_offset'

    Returns: (particles_out, lost_flag, lost_element, lost_plane)

    particles_out -- 6D position for each particle at entrance of each element.
                     The structure of 'particles_out' depends on inputs
                     'particles' and 'indices'. If 'indices' is 'None' then only
                     tracked positions at the end of the line are returned.
                     There are still two possibilities for the structure of
                     particles_out, depending on 'particles':

                    (1) if 'particles' is a single particle defined as a python
                        list of coordinates, 'particles_out' will also be a
                        simple list:
                        ex.:particles = [rx1,px1,ry1,py1,de1,dl1]
                            indices = 'None'
                            particles_out=numpy.array([rx2,px2,ry2,py2,de2,dl2])

                    (2) if 'particles' is either a python list of particles or a
                        numpy matrix then 'particles_out' will be a matrix
                        (numpy array of arrays) whose first index selects the
                        coordinate rx, px, ry, py, de or dl, in this order, and
                        the second index selects a particular particle.
                        ex.:particles = [[rx1,px1,ry1,py1,de1,dl1],
                                         [rx2,px2,ry2,py2,de2,dl2]]
                            indices = None
                            particles_out = numpy.array([[rx3, rx4],
                                                         [px3, px4],
                                                         [ry3, ry4],
                                                         [py3, py4],
                                                         [de3, de4],
                                                         [dl3, dl4]])

                    Now, if 'indices' is not 'None' then 'particles_out' can be
                    either

                    (3) a numpy matrix, when 'particles' is a single particle
                        defined as a python list. The first index of
                        'particles_out' runs through theparticle coordinate and
                        the second through the element index

                    (4) a numpy rank-3 tensor, when 'particles' is the initial
                        positions of many particles. The first index now is the
                        element index at whose exits particles coordinates are
                        returned, the second index runs through coordinates in
                        phase space and the third index runs through particles.

    lost_flag    -- a general flag indicating whether there has been particle
                    loss.
    lost_element -- list of element index where each particle was lost
                    If the particle survived the tracking through the line its
                    corresponding element in this list is set to 'None'. When
                    there is only one particle defined as a python list (not as
                    a numpy matrix with one column) 'lost_element' returns a
                    single number.
    lost_plane   -- list of strings representing on what plane each particle
                    was lost while being tracked. If the particle is not lost
                    then its corresponding element in the list is set to 'None'.
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
        particles_out = _numpy.ones((6,particles.shape[1]))
    else:
        particles_out = _numpy.zeros((len(indices),6,particles.shape[1]))
    particles_out.fill(float('nan'))


    lost_flag = False
    lost_element, lost_plane = [], []

    # loop over particles
    for i in range(particles.shape[1]):

        # python particle pos -> trackcpp particle pos
        args.element_offset = element_offset
        p_in = _Numpy2CppDoublePos(particles[:,i])
        p_out = _trackcpp.CppDoublePosVector()

        # tracking
        if _trackcpp.track_linepass_wrapper(accelerator._accelerator,
                                            p_in, p_out, args):
            lost_flag = True

        # trackcpp particle pos -> python particle pos
        if indices is None:
            particles_out[:,i] = _CppDoublePos2Numpy(p_out[0])
        else:
            for j in range(len(indices)):
                particles_out[j,:,i] = _CppDoublePos2Numpy(p_out[1+indices[j]])

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
            particles_out = particles_out[:,:,0]
        else:
            particles_out = particles_out[:,0]
        lost_element = lost_element[0]
        lost_plane = lost_plane[0]

    return particles_out, lost_flag, lost_element, lost_plane


@_interactive
def ringpass(accelerator, particles, nr_turns = 1,
             turn_by_turn = False, element_offset=0):
    """Track particle(s) along a ring.

    Accepts one or multiple particles initial positions. In the latter case,
    a list of particles or a numpy 2D array (with particle as second index)
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
                        ex.3: particles = numpy.zeros((6,Np))
    nr_turns       -- number of turns around ring to track each particle.
    turn_by_turn   -- flag indicating whether turn by turn positions are to
                      be returned. If 'False' only the positions after
                      'nr_turns' are returned.
    element_offset -- element offset (default 0) for tracking. tracking will
                      start at the element with index 'element_offset'

    Returns: (particles_out, lost_flag, lost_turn, lost_element, lost_plane)

    particles_out -- 6D position for each particle at end of ring. The structure
                     of 'particles_out' depends on inputs 'particles' and
                     'turn_by_turn'. If 'turn_by_turn' is 'False' then only
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
                             particles_out = numpy.array([[rx3, rx4],
                                                          [px3, px4],
                                                          [ry3, ry4],
                                                          [py3, py4],
                                                          [de3, de4],
                                                          [dl3, dl4]])

                     Now, if 'turn_by_turn' is 'True' then 'particles_out' can
                     be either

                    (3) a numpy matrix, when 'particles' is a single particle
                        defined as a python list. The first index of
                        'particles_out' runs through turn index and the second
                        through the particle coordinate rx, px, ry, py, de or dl

                    (4) a numpy rank-3 tensor, when 'particles' is the initial
                        positions of many particles. The first index still runs
                        through turns, while the second runs through the
                        particles coordinate and the third runs through the
                        particles indices.

    lost_flag    -- a general flag indicating whether there has been particle
                    loss.
    lost_turn    -- list of turn index where each particle was lost.
    lost_element -- list of element index where each particle was lost
                    If the particle survived the tracking through the ring its
                    corresponding element in this list is set to 'None'. When
                    there is only one particle defined as a python list (not as
                    a numpy matrix with one column) 'lost_element' returns a
                    single number.
    lost_plane   -- list of strings representing on what plane each particle
                    was lost while being tracked. If the particle is not lost
                    then its corresponding element in the list is set to 'None'.
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
        particles_out = _numpy.zeros((nr_turns,6,particles.shape[1]))
    else:
        particles_out = _numpy.zeros((6,particles.shape[1]))
    particles_out.fill(float('nan'))
    lost_flag = False
    lost_turn, lost_element, lost_plane = [], [], []

    # static parameters of ringpass
    args = _trackcpp.RingPassArgs()
    args.nr_turns = nr_turns
    args.trajectory = turn_by_turn

    # loop over particles
    for i in range(particles.shape[1]):

        # python particle pos -> trackcpp particle pos
        args.element_offset = element_offset
        p_in = _Numpy2CppDoublePos(particles[:,i])
        p_out = _trackcpp.CppDoublePosVector()

        # tracking
        if _trackcpp.track_ringpass_wrapper(accelerator._accelerator,
                                            p_in, p_out, args):
            lost_flag = True

        # trackcpp particle pos -> python particle pos
        if turn_by_turn:
            for n in range(nr_turns):
                particles_out[n,:,i] = _CppDoublePos2Numpy(p_out[n])
        else:
            particles_out[:,i] = _CppDoublePos2Numpy(p_out[0])

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
            particles_out = particles_out[:,:,0]
        else:
            particles_out = particles_out[:,0]
        lost_turn = lost_turn[0]
        lost_element = lost_element[0]
        lost_plane = lost_plane[0]

    return particles_out, lost_flag, lost_turn, lost_element, lost_plane


@_interactive
def set4dtracking(accelerator):
    accelerator.cavity_on = False
    accelerator.radiation_on = False


@_interactive
def set6dtracking(accelerator):
    accelerator.cavity_on = True
    accelerator.radiation_on = True


@_interactive
def findorbit6(accelerator, indices=None, fixed_point_guess=None):
    """Calculate 6D orbit closed-orbit.

    Accepts an optional list of indices of ring elements where closed-orbit
    coordinates are to be returned. If this argument is not passed closed-orbit
    positions are returned at the start of every element.

    Keyword arguments:
    accelerator -- Accelerator object

    Returns:
    orbit -- 6D position at elements

    Raises TrackingException
    """

    if fixed_point_guess is None:
        fixed_point_guess = _trackcpp.CppDoublePos()
    else:
        fixed_point_guess = _Numpy2CppDoublePos(fixed_point_guess)

    #_print_CppDoublePos(fixed_point_guess)
    _closed_orbit = _trackcpp.CppDoublePosVector()
    r = _trackcpp.track_findorbit6(accelerator._accelerator, _closed_orbit, fixed_point_guess)
    if r > 0:
        raise TrackingException(_trackcpp.string_error_messages[r])

    closed_orbit = _CppDoublePosVector2Numpy(_closed_orbit, indices)
    return closed_orbit


@_interactive
def findm66(accelerator, closed_orbit = None):
    """Calculate accumulatep_in = _trackcpp.DoublePos()
        p_in.rx,p_in.px,p_in.ry,p_in.py,p_in.dl,p_in.de = pos[:,i]
    matrices -- array of matrices along accelerator elements

    Raises TrackingException
    """
    if closed_orbit is None:
        closed_orbit = _trackcpp.CppDoublePosVector()
        r = _trackcpp.track_findorbit6(accelerator._accelerator, closed_orbit)
        if r > 0:
            raise TrackingException(_trackcpp.string_error_messages[r])
    else:
        if closed_orbit.shape[1] != len(accelerator):
            closed_orbit = _trackcpp.CppDoublePosVector()

    m66 = _trackcpp.CppDoubleMatrixVector()
    r = _trackcpp.track_findm66(accelerator._accelerator, closed_orbit, m66)
    if r > 0:
        raise TrackingException(_trackcpp.string_error_messages[r])

    m66_out = []
    for i in range(len(m66)):
        m = _numpy.zeros((6,6))
        for r in range(6):
            for c in range(6):
                m[r,c] = m66[i][r][c]
        m66_out.append(m)

    return m66_out

def _Numpy2CppDoublePos(p_in):
    p_out = _trackcpp.CppDoublePos()
    p_out.rx, p_out.px = float(p_in[0]), float(p_in[1])
    p_out.ry, p_out.py = float(p_in[2]), float(p_in[3])
    p_out.de, p_out.dl = float(p_in[4]), float(p_in[5])
    return p_out

def _CppDoublePos2Numpy(p_in):
    return (p_in.rx,p_in.px,p_in.ry,p_in.py,p_in.de,p_in.dl)

def _CppDoublePosVector2Numpy(orbit, indices):

    if indices == 'all':
        _indices = range(len(orbit))
    elif indices is None:
        _indices = [len(orbit)-1]
    elif isinstance(indices,int):
        _indices = [indices]

    orbit_out = _numpy.zeros((len(_indices), 6))
    for i in range(len(_indices)):
        orbit_out[i,:] = [
            orbit[_indices[i]].rx, orbit[_indices[i]].px,
            orbit[_indices[i]].ry, orbit[_indices[i]].py,
            orbit[_indices[i]].de, orbit[_indices[i]].dl
        ]
    if indices is None:
        return orbit_out[0,:]
    else:
        return orbit_out

def _Numpy2CppDoublePosVector(orbit):
    orbit_out = _trackcpp.CppDoublePosVector()
    for i in range(orbit.shape[1]):
        orbit_out.push_back(_trackcpp.CppDoublePos(
            orbit[0,i], orbit[1,i],
            orbit[2,i], orbit[3,i],
            orbit[4,i], orbit[5,i]))
    return orbit_out

def _process_args(accelerator, pos, indices=None):

    # checks whether single or multiple particles
    return_ndarray = True
    if isinstance(pos, (list,tuple)):
        if isinstance(pos[0], (list,tuple)):
            pos = _numpy.transpose(_numpy.array(pos))
        else:
            pos = _numpy.transpose(_numpy.array(pos,ndmin=2))
            return_ndarray = False
    if indices == 'all':
        indices = range(len(accelerator))

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
