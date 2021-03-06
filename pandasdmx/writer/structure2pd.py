# pandaSDMX is licensed under the Apache 2.0 license a copy of which
# is included in the source distribution of pandaSDMX.
# This is notwithstanding any licenses of third-party software included in
# this distribution.
# (c) 2014, 2015 Dr. Leo <fhaxbox66qgmail.com>


'''
This module contains a writer class that writes artefacts from a StructureMessage to
pandas dataFrames. This is useful, e.g., to visualize
codes from a codelist or concepts from a concept scheme. The writer is more general though: It can
output any collection of nameable SDMX objects.
'''

from pandasdmx.utils import DictLike
from pandasdmx.writer import BaseWriter
import pandas as PD
import numpy as NP
from itertools import chain, repeat
from operator import attrgetter


class Writer(BaseWriter):

    _row_content = {'codelists', 'conceptschemes', 'dataflows',
                    'categoryschemes', 'dimensions', 'attributes'}

    def write(self, source=None, rows=None, **kwargs):
        '''
        Transfform a collection of nameable SDMX objects 
        from a :class:`pandasdmx.model.StructureMessage` instance to a pandas DataFrame.

        Args:
            source(pandasdmx.model.StructureMessage): a :class:`pandasdmx.model.StructureMessage` 

            rows(str): sets the desired content 
                to be extracted from the StructureMessage.
                Must be a name of an attribute of the StructureMessage. The attribute must
                be an instance of `dict` whose keys are strings. These will be
                interpreted as ID's and used for the MultiIndex of the DataFrame
                to be returned. Values can be either instances of `dict` such as for codelists, or simple nameable objects
                such as for dataflows. In the latter case, the DataFrame will have a flat index.  
                (default: depends on content found in Message. 
                Common is 'codelists')
            columns(str, list): if str, it denotes the only attribute of the
                values (nameable SDMX objects such as Code or ConceptScheme) that will be stored in the
                DataFrame. If a list, it must contain strings
                that are valid attibute values. Defaults to: ['name', 'description']
        '''

        # Set convenient default values for args
        # is rows a string?
        if rows is not None and not isinstance(rows, (list, tuple)):
            rows = [rows]
            return_df = True
        elif isinstance(rows, (list, tuple)) and len(rows) == 1:
            return_df = True
        else:
            return_df = False
        if rows is None:
            rows = [i for i in self._row_content if hasattr(source, i)]
        # Generate the DataFrame or -Frames and store them in a DictLike with
        # content-type names as keys
        frames = DictLike(
            {r: self._make_dataframe(source, r, **kwargs) for r in rows})
        if return_df:
            # There is only one item. So return the only value.
            return frames.any()
        else:
            return frames

    def _make_dataframe(self, source, rows, constraint=None,
                        dimensions_only=False, columns=['name'], lang='en'):

        def get_data(scheme, item):
            if scheme is item:
                raw = [getattr(scheme, s) for s in columns]
            else:
                # Prepare for flat list where item is None and all the
                # gist is in scheme.
                if item is None:
                    item = scheme
                raw = [getattr(item, s)
                       for s in columns]
            # Select language for international strings represented as dict
            translated = tuple(s[lang] if lang in s else s['en'] for s in raw)
            if len(translated) > 1:
                return translated
            else:
                return translated[0]

        def iter_keys(container):
            if rows == 'codelists' and constraint:
                try:
                    dim_id = cl2dim[container.id]
                    result = (
                        v for v in container.values() if (dim_id, v.id) in constraint)
                except KeyError:
                    pass
            result = container.values()
            return sorted(result, key=attrgetter('id'))

        def iter_schemes():
            # iterate only over codelists representing dimensions?
            # check tis condition. is rows correct?
            if rows == 'codelists' and dimensions_only:
                raw = (i for i in content.values() if i.id in cl2dim)
            else:
                raw = content.values()
            return sorted(raw, key=attrgetter('id'))

        if rows == 'codelists':
            dsd = source.datastructures.any()
            # Dimensions represented by the code lists
            dimensions = [d for d in dsd.dimensions.aslist() if d.id not in
                          ['TIME', 'TIME_PERIOD']]
            # map codelist ID's to dimension names of the DSD.
            # This is needed to efficiently check for any constraint
            cl2dim = {d.local_repr.enum.id: d.id for d in dimensions}
            if constraint:
                try:
                    # use any user-provided constraint
                    constraint = constraint.constraints.any()
                except AttributeError:
                    # So the Message must containe one
                    constraint = source.constraints.any()
                # We assume that where there's a code list, a DSD is not far.

        # allow `columns` arg to be a str
        if not isinstance(columns, (list, tuple)):
            columns = [columns]

        content = getattr(source, rows)
        # Distinguish hierarchical content consisting of a dict of dicts, and
        # flat content consisting of a dict of atomic values. In the former case,
        # the resulting DataFrame will have 2 index levels.
        if isinstance(content.any(), dict):
            # generate index
            raw_tuples = chain(*(zip(
                # 1st index level eg codelist ID
                repeat(container),
                # 2nd index level: first row in each codelist is the corresponding
                # dimension name. The following rows are code ID's. Hence the chain.
                # Need to access cl2dim and make cl2attr.
                chain((container,), iter_keys(container)))
                for container in iter_schemes()))
            # Now actually generate the index
            raw_idx, data = zip(*(((i.id, '__' + j.id) if i is j else (i.id, j.id),
                                   get_data(i, j))
                                  for i, j in raw_tuples))
            idx = PD.MultiIndex.from_tuples(raw_idx)  # set names?
        else:
            # flatt structure, e.g., dataflow definitions
            raw_tuples = sorted(content.values(), key=attrgetter('id'))
            raw_idx, data = zip(*((t.id, get_data(t, None))
                                  for t in raw_tuples))  # pass '_' to get_data?
            idx = PD.Index(raw_idx, name=rows)
        return PD.DataFrame(NP.array(data), index=idx, columns=columns)
