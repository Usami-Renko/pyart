"""
pyart.io.auto_read
==================

Automatic reading of radar files by detecting format.

.. autosummary::
    :toctree: generated/

    read
    determine_filetype

"""

import bz2

import netCDF4

from . import _RSL_AVAILABLE
if _RSL_AVAILABLE:
    from .rsl import read_rsl
from .mdv import read_mdv
from .cfradial import read_cfradial
from .sigmet import read_sigmet
from .nexrad_archive import read_nexrad_archive
from .nexrad_cdm import read_nexrad_cdm


def read(filename, use_rsl=False, **kwargs):
    """
    Read a radar file and return a radar object.

    Additional parameters are passed to the underlying read_* function.

    Parameters
    ----------
    filename : str
        Name of radar file to read
    use_rsl : bool
        True will use the TRMM RSL library to read files which are supported
        both natively and by RSL.  False will choose the native read function.
        RSL will always be used to read a file if it is not supported
        natively.

    Other Parameters
    -------------------
    field_names : dict, optional
        Dictionary mapping file data type names to radar field names. If a
        data type found in the file does not appear in this dictionary or has
        a value of None it will not be placed in the radar.fields dictionary.
        A value of None, the default, will use the mapping defined in the
        metadata configuration file.
    additional_metadata : dict of dicts, optional
        Dictionary of dictionaries to retrieve metadata from during this read.
        This metadata is not used during any successive file reads unless
        explicitly included.  A value of None, the default, will not
        introduct any addition metadata and the file specific or default
        metadata as specified by the metadata configuration file will be used.
    file_field_names : bool, optional
        True to use the file data type names for the field names. If this
        case the field_names parameter is ignored. The field dictionary will
        likely only have a 'data' key, unless the fields are defined in
        `additional_metadata`.
    exclude_fields : list or None, optional
        List of fields to exclude from the radar object. This is applied
        after the `file_field_names` and `field_names` parameters.

    Returns
    -------
    radar : Radar
        Radar object.  A TypeError is raised if the format cannot be
        determined.

    """
    filetype = determine_filetype(filename)

    # Bzip, uncompress and see if we can determine the type
    if filetype == 'BZ2':
        filetype = determine_filetype(bz2.BZ2File(filename))

    # Py-ART only supported formats
    if filetype == "MDV":
        return read_mdv(filename, **kwargs)
    if filetype == "NETCDF3" or filetype == "NETCDF4":
        dset = netCDF4.Dataset(filename)
        if 'cdm_data_type' in dset.ncattrs():   # NEXRAD CDM
            return read_nexrad_cdm(filename, **kwargs)
        else:
            return read_cfradial(filename, **kwargs)    # CF/Radial
    if filetype == 'WSR88D':
        return read_nexrad_archive(filename, **kwargs)

    # RSL supported formats which are also supported natively in Py-ART
    if filetype == "SIGMET":
        if use_rsl:
            return read_rsl(filename, **kwargs)
        else:
            return read_sigmet(filename, **kwargs)

    # RSL only supported file formats
    rsl_formats = ['UF', 'HDF4', 'RSL', 'DORAD', 'LASSEN']
    if filetype in rsl_formats and _RSL_AVAILABLE:
        return read_rsl(filename, **kwargs)

    raise TypeError('Unknown or unsupported file format: ' + filetype)


def determine_filetype(filename):
    """
    Return the filetype of a given file by examining the first few bytes.

    The following filetypes are detected:

    * 'MDV'
    * 'NETCDF3'
    * 'NETCDF4'
    * 'WSR88D'
    * 'UF'
    * 'HDF4'
    * 'RSL'
    * 'DORAD'
    * 'SIGMET'
    * 'LASSEN'
    * 'BZ2'
    * 'UNKNOWN'

    Parameters
    ----------
    filename : str
        Name of file to examine.

    Returns
    -------
    filetype : str
        Type of file.

    """
    # TODO
    # detect the following formats, those supported by RSL
    # 'RADTEC', the SPANDAR radar at Wallops Island, VA
    # 'MCGILL', McGill S-band
    # 'TOGA', DYNAMO project's radar
    # 'RAPIC', Berrimah Australia
    # 'RAINBOW'

    # read the first 12 bytes from the file
    try:
        f = open(filename, 'rb')
    except TypeError:
        f = filename
    begin = f.read(12)
    f.close()

    # MDV, read with read_mdv
    # MDV format signature from MDV FORMAT Interface Control Document (ICD)
    # recond_len1, struct_id, revision_number
    # 1016, 14142, 1
    # import struct
    # mdv_signature = struct.pack('>3i', 1016, 14142, 1)
    mdv_signature = '\x00\x00\x03\xf8\x00\x007>\x00\x00\x00\x01'
    if begin[:12] == mdv_signature:
        return "MDV"

    # NetCDF3, read with read_cfradial
    if begin[:3] == "CDF":
        return "NETCDF3"

    # NetCDF4, read with read_cfradial, contained in a HDF5 container
    # HDF5 format signature from HDF5 specification documentation
    hdf5_signature = '\x89\x48\x44\x46\x0d\x0a\x1a\x0a'
    if begin[:8] == hdf5_signature:
        return "NETCDF4"

    # Other files should be read with read_rsl
    # WSR-88D begin with ARCHIVE2. or AR2V000
    if begin[:9] == 'ARCHIVE2.' or begin[:7] == 'AR2V000':
        return "WSR88D"

    # Universal format has UF in bytes 0,1 or 2,3 or 4,5
    if begin[:2] == "UF" or begin[2:4] == "UF" or begin[4:6] == "UF":
        return "UF"

    # DORADE files
    if begin[:4] == "SSWB" or begin[:4] == "VOLD" or begin[:4] == "COMM":
        return "DORADE"

    # LASSEN
    if begin[4:11] == 'SUNRISE':
        return "LASSEN"

    # RSL file
    if begin[:3] == "RSL":
        return "RSL"

    # HDF4 file
    # HDF4 format signature from HDF4 specification documentation
    hdf4_signature = '\x0e\x03\x13\x01'
    if begin[:4] == hdf4_signature:
        return "HDF4"

    # SIGMET files
    # SIGMET format is a structure_header with a Product configuration
    # indicator (see section 4.2.47)
    # sigmet_signature = chr(27)
    sigmet_signature = '\x1b'
    if begin[0] == sigmet_signature:
        return "SIGMET"

    # bzip2 compressed files
    bzip2_signature = 'BZh'
    if begin[:3] == bzip2_signature:
        return 'BZ2'

    # Cannot determine filetype
    return "UNKNOWN"
