# -*- coding: utf-8 -*-
import warnings
warnings.filterwarnings("once", category=DeprecationWarning)  # noqa

import os
import re
import glob

# Libs
import pandas as pd
from jinja2 import Environment, FileSystemLoader
import pickle
import numpy as np

# Local imports
from oggm import utils
from mbcrossval.plots import crossval_timeseries, crossval_histogram
from mbcrossval.plots import crossval_boxplot
from mbcrossval import mbcfg


def website_main():
    # setup jinja
    file_loader = FileSystemLoader(mbcfg.PATHS['jinjadir'])
    env = Environment(loader=file_loader)

    # first clean all potential old html files
    files = glob.glob(mbcfg.PATHS['webroot'] + '/**/*.html', recursive=True)
    for fl in files:
        os.remove(fl)

    # make a catalogue from all stored versions
    vdf = catalog_storaged_files()

    # make a dictonary with the latest versions vor linking
    nbpaths = {}
    for vers in vdf.keys():
        try:
            vpath = vdf[vers].iloc[-1].version
        except IndexError:
            vpath = ''
        nbpaths[vers] = os.path.join(vpath, '%s.html' % vers)
        nbpaths['webroot'] = 'index.html'

    # create index page
    create_index(env, nbpaths)

    if mbcfg.PARAMS['redo_all_plots']:
        redo_all_plots(vdf)

    # split all available files and process seperately:
    # global reference glaciers, short crossvalidation
    create_minor_website(env, vdf['cru_short'], 'cru_short.html', nbpaths)
    # global reference glaciers, extended crossvalidation
    create_major_website(env, vdf['cru_extended'], 'cru_extended.html',
                         nbpaths)
    # HISTALP reference glaciers, short crossvalidation
    create_minor_website(env, vdf['histalp_short'], 'histalp_short.html',
                         nbpaths)
    # HISTALP reference glaciers, extended crossvalidation
    create_major_website(env, vdf['histalp_extended'], 'histalp_extended.html',
                         nbpaths)


def create_index(env, nbpaths):

    template = env.get_template('index.html')
    index = template.render(nbpaths=nbpaths)
    indexfile = os.path.join(mbcfg.PATHS['webroot'], 'index.html')

    with open(indexfile, 'w') as fl:
        fl.write(index)


def redo_all_plots(vdf_dict):
    """
    This function will redo all crossvalidation plots. Time consuming!


    Sometimes its necessary to redo all crossvalidation plots.
    E.g. if you want to change the appearence of a plot.

    Parameters
    ----------
    vdf_dict: Dict of pandas.DataFrames
        containing all necessary information
    """

    for vdf in vdf_dict.values():
        for nr, df in vdf.iterrows():

            utils.mkdir(df['pd'])

            # make minor plots
            if df.min_maj == 'minor':
                # try to make plots
                crossval_timeseries(df.file, df.pd)
                crossval_histogram(df.file, df.pd)

            elif df.min_maj == 'major':
                crossval_boxplot(df.file, df.pd)


def catalog_storaged_files():
    """
    List all finished crossvalidations available in STORAGE in a DataFrame

    Returns vdf, pandas.DataFrame
        The DataFrame containing information on the specific run
    -------

    """
    vdf = pd.DataFrame([], columns=['version', 'min_maj', 'file',
                                    'wd', 'pd'])

    for x in os.listdir(mbcfg.PATHS['storage_dir']):
        parts = x.split('_')

        webdir = os.path.join(mbcfg.PATHS['webroot'], parts[1], 'web')
        pltdir = os.path.join(mbcfg.PATHS['webroot'], parts[1], 'plots')

        vdf = vdf.append({'version': parts[1],
                          'min_maj': parts[2].split('.')[0],
                          'file': os.path.join(mbcfg.PATHS['storage_dir'], x),
                          'wd': webdir,
                          'verdir': os.path.join(mbcfg.PATHS['webroot'],
                                                 parts[1]),
                          'pd': pltdir,
                          'histalp': 'histalp' in parts[1]},
                         ignore_index=True)

    # make a integer version column for easier sorting
    int_version = [re.split('\W+', x)[:4] for x in vdf.version]
    vdf['int_version'] = np.array(int_version, dtype=int).tolist()
    vdf = vdf.sort_values(by='int_version')

    # and split them into the 4 main different combinations for better handling
    # CRU short
    cru_short = vdf.loc[(vdf.histalp == 1) & (vdf.min_maj == 'minor')]
    cru_short.index = np.arange(len(cru_short))
    # CRU extended
    cru_extended = vdf.loc[(vdf.histalp == 0) & (vdf.min_maj == 'major')]
    cru_extended.index = np.arange(len(cru_extended))
    # HITALP short
    histalp_short = vdf.loc[(vdf.histalp == 1) & (vdf.min_maj == 'minor')]
    histalp_short.index = np.arange(len(histalp_short))
    # HISTALP extended
    histalp_extended = vdf.loc[(vdf.histalp == 0) & (vdf.min_maj == 'major')]
    histalp_extended.index = np.arange(len(histalp_extended))

    return {'cru_short': cru_short, 'histalp_short': histalp_short,
            'cru_extended': cru_extended, 'histalp_extended': histalp_extended}


def create_major_website(env, vdf, templatefile, nbpaths):
    if vdf.empty:
        # only create simple website
        template = env.get_template(templatefile)
        tmpl = template.render(hasdata=0,
                               nbpaths=nbpaths)
        tmplfile = os.path.join(mbcfg.PATHS['webroot'], templatefile)

        with open(tmplfile, 'w') as fl:
            fl.write(tmpl)

    else:
        # the real deal
        # alter the links of the navbar
        nbpaths1 = nbpaths.copy()
        linksuffix = '../'
        for key in nbpaths.keys():
            nbpaths1[key] = linksuffix + nbpaths[key]

        for nr, vers in vdf.iterrows():

            # read data
            xvaldict = pickle.load(open(vers['file'], 'rb'))

            #
            # WRITE ACTUAL HTML FILES
            template = env.get_template(templatefile)
            fallback = env.get_template('fallback.html')

            htmlname = os.path.join(vers['verdir'], templatefile)

            # path to where the crossval plots SHOULD BE stored
            cvplots = [x for x in os.listdir(vers['pd'])
                       if 'crossval' in x]
            if len(cvplots) == 0:
                raise RuntimeError('No extended crossval plots available!')

            #
            # Add PREVIOUS/NEXT buttons and link them
            if (vers == vdf.iloc[0]).all() & (len(vdf) > 1):
                # first version, no previous
                previous = ''
                nxtlink = os.path.join(linksuffix, vdf.iloc[nr+1]['version'],
                                       templatefile)
                nxtfile = os.path.join(mbcfg.PATHS['webroot'],
                                       vdf.iloc[nr+1]['version'],
                                       templatefile)

                next = '<a href="%s" class="next">%s &raquo;</a>' % \
                       (nxtlink, vdf.iloc[nr+1]['version'])
                if not os.path.isfile(nxtfile):
                    fbhtml = fallback.render()
                    with open(nxtfile, 'w') as fb:
                        fb.write(fbhtml)

            elif (vers == vdf.iloc[-1]).all() & (len(vdf) > 1):
                # last version, no next
                next = ''
                prvlink = os.path.join(linksuffix, vdf.iloc[nr-1]['version'],
                                       templatefile)
                prvfile = os.path.join(mbcfg.PATHS['webroot'],
                                       vdf.iloc[nr-1]['version'],
                                       templatefile)

                previous = '<a href="%s" class="previous">&laquo; %s</a>' % \
                           (prvlink, vdf.iloc[nr-1]['version'])
                if not os.path.isfile(prvfile):
                    fbhtml = fallback.render()
                    with open(prvfile, 'w') as fb:
                        fb.write(fbhtml)

            elif len(vdf) == 1:
                next = ''
                previous = ''
            else:
                nxtlink = os.path.join(linksuffix, vdf.iloc[nr+1]['version'],
                                       templatefile)
                nxtfile = os.path.join(mbcfg.PATHS['webroot'],
                                       vdf.iloc[nr+1]['version'], templatefile)
                prvlink = os.path.join(linksuffix, vdf.iloc[nr-1]['version'],
                                       templatefile)
                prvfile = os.path.join(mbcfg.PATHS['webroot'],
                                       vdf.iloc[nr-1]['version'], templatefile)

                previous = '<a href="%s" class="previous">&laquo; %s</a>' % \
                           (prvlink, vdf.iloc[nr-1]['version'])
                next = '<a href="%s" class="next">%s &raquo;</a>' % \
                       (nxtlink, vdf.iloc[nr+1]['version'])
                if not os.path.isfile(nxtfile):
                    fbhtml = fallback.render()
                    with open(nxtfile, 'w') as fb:
                        fb.write(fbhtml)
                if not os.path.isfile(prvfile):
                    fbhtml = fallback.render()
                    with open(prvfile, 'w') as fb:
                        fb.write(fbhtml)

            glchtml = template.render(version=xvaldict['oggmversion'],
                                      date=xvaldict['date_created'],
                                      cvplots=cvplots,
                                      hasdata=True,
                                      previous=previous,
                                      next=next,
                                      nbpaths=nbpaths1)
            with open(htmlname, 'w') as fl:
                fl.write(glchtml)


def create_minor_website(env, vdf, templatefile, nbpaths):
    if vdf.empty:
        # only create simple website
        template = env.get_template(templatefile)
        tmpl = template.render(hasdata=0,
                               nbpaths=nbpaths)
        tmplfile = os.path.join(mbcfg.PATHS['webroot'], templatefile)

        with open(tmplfile, 'w') as fl:
            fl.write(tmpl)

    else:
        # the real deal

        # alter the links of the navbar
        nbpaths1 = nbpaths.copy()
        nbpaths2 = nbpaths.copy()
        linksuffix = '../'
        for key in nbpaths.keys():
            nbpaths1[key] = linksuffix + nbpaths[key]
            nbpaths2[key] = linksuffix + linksuffix + nbpaths[key]

        for nr, vers in vdf.iterrows():

            # read data
            xvaldict = pickle.load(open(vers['file'], 'rb'))
            df = xvaldict['per_glacier']

            # sort array
            df.sort_values('Name', inplace=True)
            # move glaciers without name to the end
            df = pd.concat([df.loc[df.Name != ''], df.loc[df.Name == '']])
            # concatenate the overview to the beginning
            df = pd.concat([pd.DataFrame([{'Name': '',
                                           'RGIId': 'Overview',
                                           'xval_bias': df.xval_bias.mean(),
                                           'tstar_bias': df.tstar_bias.mean()}
                                          ]),
                            df],
                           ignore_index=True)

            # set index to RGIId
            df.index = df.RGIId

            #
            #
            # LINKNAMEs
            df['linkname'] = df.RGIId
            df.loc[df.Name != '', 'linkname'] = df.loc[df.Name != '',
                                                       'linkname']\
                + ', ' + df.loc[df.Name != '', 'Name']

            #
            # LINKLIST for GLACIERS
            df['link'] = df.RGIId + '.html'
            df.loc['Overview', 'link'] = '../' + templatefile
            template = env.get_template('createlinklist.txt')
            linklist = template.render(glaciers=df.to_dict(orient='records'))
            with open(os.path.join(mbcfg.PATHS['jinjadir'], 'linklist.html'),
                      'w') as fl:
                fl.write(linklist)

            #
            # LINKLIST for INDEX
            df['link'] = 'web/' + df.RGIId + '.html'
            df.loc['Overview', 'link'] = templatefile
            linklist = template.render(glaciers=df.to_dict(orient='records'))
            with open(os.path.join(mbcfg.PATHS['jinjadir'],
                                   'linklistindex.html'),
                      'w') as fl:
                fl.write(linklist)

            #
            # WRITE ACTUAL HTML FILES
            template = env.get_template(templatefile)
            fallback = env.get_template('fallback.html')
            for idx, glc in df.iterrows():

                # DIFFERENT VALUES DEPENDING ON INDEX OR GLACIER
                if glc.RGIId == 'Overview':
                    # first: index page
                    bias1 = '  Mean t_star bias:'.ljust(27) + \
                            "{0:5.1f}".format(glc['tstar_bias'])
                    bias2 = 'Mean crossval bias:'.ljust(27) + \
                            "{0:5.1f}".format(glc['xval_bias'])

                    htmlname = os.path.join(vers['verdir'], templatefile)
                    imgname = 'plots/mb_histogram.png'
                    index = 1
                    linksuffix = '../'
                    nbpath_use = nbpaths1

                else:
                    # second: glacier specific page
                    bias1 = '    Calibrated MB bias:'.ljust(35) + \
                            "{0:5.6f}".format(glc['tstar_bias'])
                    bias2 = 'Crossvalidated MB bias:'.ljust(35) + \
                            "{0:5.1f}".format(glc['xval_bias'])

                    htmlname = os.path.join(vers['wd'], glc['RGIId']) + '.html'
                    imgname = '../plots/%s.png' % glc['RGIId']
                    index = 0
                    linksuffix = '../../'
                    nbpath_use = nbpaths2

                #
                # Add PREVIOUS/NEXT buttons and link them
                if (vers == vdf.iloc[0]).all() & (len(vdf) > 1):
                    # first version, no previous
                    previous = ''
                    nxtlink = os.path.join(linksuffix,
                                           vdf.iloc[nr+1]['version'],
                                           glc['link'])
                    nxtfile = os.path.join(mbcfg.PATHS['webroot'],
                                           vdf.iloc[nr+1]['version'],
                                           glc['link'])

                    next = ('<a href="%s" class="next">%s &raquo;</a>' %
                            (nxtlink, vdf.iloc[nr+1]['version']))
                    if not os.path.isfile(nxtfile):
                        fbhtml = fallback.render()
                        with open(nxtfile, 'w') as fb:
                            fb.write(fbhtml)

                elif (vers == vdf.iloc[-1]).all() & (len(vdf) > 1):
                    # last version, no next
                    next = ''
                    prvlink = os.path.join(linksuffix,
                                           vdf.iloc[nr-1]['version'],
                                           glc['link'])
                    prvfile = os.path.join(mbcfg.PATHS['webroot'],
                                           vdf.iloc[nr-1]['version'],
                                           glc['link'])

                    previous = ('<a href="%s" class="previous">&laquo; %s</a>'
                                % (prvlink, vdf.iloc[nr-1]['version']))
                    if not os.path.isfile(prvfile):
                        fbhtml = fallback.render()
                        with open(prvfile, 'w') as fb:
                            fb.write(fbhtml)

                elif len(vdf) == 1:
                    next = ''
                    previous = ''
                else:
                    nxtlink = os.path.join(linksuffix,
                                           vdf.iloc[nr+1]['version'],
                                           glc['link'])
                    nxtfile = os.path.join(mbcfg.PATHS['webroot'],
                                           vdf.iloc[nr+1]['version'],
                                           glc['link'])
                    prvlink = os.path.join(linksuffix,
                                           vdf.iloc[nr-1]['version'],
                                           glc['link'])
                    prvfile = os.path.join(mbcfg.PATHS['webroot'],
                                           vdf.iloc[nr-1]['version'],
                                           glc['link'])

                    previous = ('<a href="%s" class="previous">&laquo; %s</a>'
                                % (prvlink, vdf.iloc[nr-1]['version']))
                    next = ('<a href="%s" class="next">%s &raquo;</a>' %
                            (nxtlink, vdf.iloc[nr+1]['version']))
                    if not os.path.isfile(nxtfile):
                        fbhtml = fallback.render()
                        with open(nxtfile, 'w') as fb:
                            fb.write(fbhtml)
                    if not os.path.isfile(prvfile):
                        fbhtml = fallback.render()
                        with open(prvfile, 'w') as fb:
                            fb.write(fbhtml)

                glchtml = template.render(glcname=glc['linkname'],
                                          glcimg=imgname,
                                          version=xvaldict['oggmversion'],
                                          date=xvaldict['date_created'],
                                          bias1=bias1,
                                          bias2=bias2,
                                          index=index,
                                          previous=previous,
                                          next=next,
                                          nbpaths=nbpath_use,
                                          hasdata=True)
                with open(htmlname, 'w') as fl:
                    fl.write(glchtml)
