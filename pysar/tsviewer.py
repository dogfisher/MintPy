#! /usr/bin/env python
############################################################
# Program is part of PySAR v1.0                            #
# Copyright(c) 2013, Heresh Fattahi                        #
# Author:  Heresh Fattahi                                  #
############################################################
# Yunjun, Aug 2015: Add minDate/maxDate/excludeDateList/contour option
#                   Add radius option and errorbar in the plot
# Yunjun, Sep 2015: Add x/y/dispVelFig/dispTsFig option
# Yunjun, Jun 2016: Add date_list2vector(), check_yx(), read_dis()
#                   Add reference point display
#                   Add plot_ts(), adjust_xaxis_date()
# Yunjun, Jul 2016: Support reference date input


import sys
import os
import getopt
import time
import datetime

import h5py
import numpy as np
import scipy.io as sio
import scipy.stats as stats

import matplotlib.dates as mdates
import matplotlib.patches as patches      # need for draw rectangle of points selected on VelFig
import matplotlib.pyplot as plt

import pysar._readfile as readfile
import pysar._datetime as ptime
from pysar.view import orbit_direction


################################## Sub Functions ###################################
################################################################
def check_yx(xsub,ysub,radius,ax):
  ##### Read Y/X
  try:     xmin=xsub[0];         xmax=xsub[1]+1;       
  except:  xmin=xsub[0]-radius;  xmax=xsub[0]+radius+1;
  try:     ymin=ysub[0];         ymax=ysub[1]+1;       
  except:  ymin=ysub[0]-radius;  ymax=ysub[0]+radius+1;

  ## mark x/y in Fig 1
  rectSelect=patches.Rectangle((xmin,ymin),xmax-xmin,ymax-ymin,color=rectColor,fill=False,lw=1.5)
  ax.add_patch(rectSelect)

  return [xmin,xmax],[ymin,ymax]

################################################################
def read_dis(xsub,ysub,dateList,h5file,unit='cm'):
  global ref_date

  ## Unit and Scale
  if   unit == 'm' :  unitFac=1.0
  elif unit == 'mm':  unitFac=1000.0
  elif unit == 'km':  unitFac=0.001
  else:unit =  'cm';  unitFac=100.0   # cm by default

  ## read displacement
  try:
      ref_date
      dis_ref = h5file['timeseries'].get(ref_date)[ysub[0]:ysub[1],xsub[0]:xsub[1]]
  except: pass

  dis=[]
  for date in dateList:
      dis0 = h5file['timeseries'].get(date)[ysub[0]:ysub[1],xsub[0]:xsub[1]]
      try: dis0 -= dis_ref
      except: pass
      dis.append(dis0)
  dis=np.array(dis)*unitFac;
  dis=np.reshape(dis,(len(dateList),-1))

  ## calculate mean
  dis_mean=stats.nanmean(dis,1)
  ## calculate standard deviation
  if (xsub[1]-xsub[0])*(ysub[1]-ysub[0]) == 1:
      dis_std = np.array([0]*len(dateList))
  else:
      dis_std = stats.nanstd(dis,1)
  ## calculate linear velocity
  dates, datevector = ptime.date_list2vector(dateList)
  dis_slope = stats.linregress(np.array(datevector),dis_mean)
  
  ## display
  print 'spatial averaged displacement ['+unit+']:'
  print dis_mean
  print 'standard deviation ['+unit+']:'
  print dis_std
  print 'linear velocity ['+unit+'/yr]:'
  print str(dis_slope[0])+'+/-'+str(dis_slope[4])

  return dis, dis_mean, dis_std, dis_slope

################################################################
def update_lim(disp_min,disp_max,data_mean,data_std):
   disp_min = np.nanmin([np.nanmin(data_mean-data_std), disp_min])
   disp_max = np.nanmax([np.nanmax(data_mean+data_std), disp_max])
   return disp_min,disp_max


####################### X Axis Format #######################
def adjust_xaxis_date(ax,datevector):
  ## Date Display
  years    = mdates.YearLocator()   # every year
  months   = mdates.MonthLocator()  # every month
  yearsFmt = mdates.DateFormatter('%Y')

  ## X axis format
  ax.fmt_xdata = mdates.DateFormatter('%Y-%m-%d %H:%M:%S')
  ts=datevector[0] -0.2;  ys=int(ts);  ms=int((ts-ys)*12)
  te=datevector[-1]+0.2;  ye=int(te);  me=int((te-ye)*12)
  if ms>12:   ys = ys+1;   ms=1
  if me>12:   ye = ye+1;   me=1
  if ms<1:    ys = ys-1;   ms=12
  if me<1:    ye = ye-1;   me=12
  dss=datetime.date(ys,ms,1)
  dee=datetime.date(ye,me,1)
  ax.set_xlim(dss,dee)                          # using the same xlim with the previous one
  ax.xaxis.set_major_locator(years)
  ax.xaxis.set_major_formatter(yearsFmt)
  ax.xaxis.set_minor_locator(months)
  for tick in ax.xaxis.get_major_ticks():  tick.label.set_fontsize(fontSize)
  #fig2.autofmt_xdate()     #adjust x overlap by rorating, may enble again

  return ax


########################## Usage ###############################
def Usage():
    print '''
*******************************************************************************************************
  Time-series Viewer

  Usage:
      tsviewer.py -f timeseriesFile.h5 -v velocityFile.h5 -l lower bound -h higher bound
                    -s fontsize -m Marker Size -c marker color -w linewidth -u unit

        -f : file of the timeseries
        -v : velocity file, or epoch_date (if not specified then the last time-series epoch is displayed)
        -l : lower bound of the displacement [default is min of the displacemen]
        -h : higher bound of the displacemet [default is max of the displacemen]
        -a : lower bound of the colorscale to display the velocity to display
        -b : higher bound of the colorscale to display the velocity to display
        -F : another  timeseries file (can be used to compare 2 time-series)

     Figure Setting
        -s : size of font used x and y labels [default = 22]
        -m : marker size [default = 16]
        -c : color of the markers [default = green]. some options are: orange, black, yellow, blue, green...
        -w : width of lines to connect the points [default = 2].
             set to 0 (-l 0) if you don't want any line connecting the points
        -u/--unit    : unit of the displacement [default = cm]. Other optons are: mm and m
        --rect-color : color of rectangle that mark the selection in velocity figure, 'crimson' by default

     XY Input
        -r : radius of selecting square in pixels, display mean value from (+/-radius,+/-radius).
             [default is 0 - one point]
        -x : x coordinate (range) of selection
        -y : y coordinate (range) of selection
        -X : x coordinate (range) of reference / comparison
        -Y : y coordinate (range) of reference / comparison

     DEM
        -D : dem file
        -C : display Contour: no, yes, or only
             ('no' for DEM only, 'yes' for DEM basemap and Contour, 'only' for contour only). [Default is 'only']
        -V : contour step for display [default is 200 m]

     Date Input
        -t : minimum date for display
        -T : maximum date for display
        -E/--exclude : exclude dates list for display
        --ref-date   : reference date for time series displacement

     Save and Output
        --save       : save data and plot                     - save timeseries data/plot
        --nodisplay  : save data and plots and do not display - save timeseries data/plot and velocity plot
                       default output filename:
                       x100_110y230_240_ts.mat
                       x100_110y230_240_ts.pdf
                       x100_110y230_240_vel.png

  Example:
        tsviewer.py timeseries.h5
        tsviewer.py -f timeseries.h5 -v velocity.h5 -a -0.01 -b 0.01
        tsviewer.py -f timeseries.h5 -v 20080929
        tsviewer.py -f timeseries.h5 -s 24 -m 12 -c orange -l -10 -h 10 -w 4 -u mm 

        tsviewer.py -f timeseries.h5 -v velocity.h5 -a -0.01 -b 0.02 -l -10 -h 10 -D Andreas.dem -C yes --save

    Exclude dates:
        tsviewer.py -f timeseries.h5 -v velocity.h5 -t 20100102 -T 20101120 -E '20100520,20100705'

    Compare two timeseries files:
        tsviewer.py -f timeseries.h5 -v velocity.h5 -F timeseries_tropCor.h5 
        tsviewer.py -f timeseries.h5 -v velocity.h5 -F timeseries.h5        -E '20100520,20100705'  

    X/Y Input:
        tsviewer.py -f timeseries.h5 -v velocity.h5 -r 10
        tsviewer.py -f timeseries.h5 -x 300 -y 500  -r 10
        tsviewer.py -f timeseries.h5 -x 300:330 -y 500:530
        tsviewer.py -f timeseries.h5 -v velocity.h5 -a -0.02 -b 0.02 -l -5 -h 5 -D Andreas.dem -C yes -x 300:330 -y 500:530 --nodisplay

*******************************************************************************************************
    '''


###############################  Main Function  ####################################

def main(argv):

  ## Default settings

  global markerSize, markderSize2, markerColor, markerColor2, rectColor
  global lineWidth, lineWidth2, edgeWidth, fontSize

  markerSize  =16
  markerSize2 =16
  markerColor ='crimson'     # g
  markerColor2='royalblue'
  markerColor3='white'
  rectColor   ='crimson'
  lineWidth   =2
  lineWidth2  =0
  edgeWidth   =1.5
  fontSize    =16


  global unit, radius, saveFig, dispFig, fig_dpi

  fig_dpi=300
  radius=0;
  saveFig = 'no'
  dispFig = 'yes'
  unit='cm'

  dispContour = 'only'
  smoothContour = 'no'
  contour_step  = 200
  showRef = 'yes'

  global ref_xsub, ref_ysub, ref_date
  global h5timeseries_2, dates_2, dateList_2
  global lbound, hbound

  ############### Check Inputs ##################
  if   len(sys.argv)< 2:   Usage(); sys.exit(1)
  elif len(sys.argv)==2:
    if argv[0]=='-h':      Usage(); sys.exit(1)
    elif os.path.isfile(argv[0]):
       timeSeriesFile = argv[0];   h5timeseries = h5py.File(timeSeriesFile);  k = h5timeseries.keys();
       if not 'timeseries' in k:   print 'ERROR: Input file is '+k[0]+'.\n\tOnly timeseries is supported.\n'; sys.exit(1)
    else:  Usage(); sys.exit(1)

  elif len(sys.argv)>2:
    try:   opts, args = getopt.getopt(argv,"f:F:v:a:b:s:m:c:w:u:l:h:D:C:V:t:T:d:r:x:y:X:Y:o:E:",
                                          ['save','nodisplay','unit=','exclude=','ref-date=','rect-color'])
    except getopt.GetoptError:    Usage() ; sys.exit(1)

    for opt,arg in opts:
      if   opt == '-f':     timeSeriesFile   = arg
      elif opt == '-F':     timeSeriesFile_2 = arg
      elif opt == '-v':     velocityFile     = arg
      elif opt == '-a':     vmin             = float(arg)
      elif opt == '-b':     vmax             = float(arg)
      elif opt == '-s':     fontSize         = int(arg)
      elif opt == '-m':     markerSize       = int(arg);       markerSize2=int(arg)
      elif opt == '-c':     markerColor      = arg
      elif opt == '-w':     lineWidth        = int(arg)
      elif opt == '-u':     unit             = arg
      elif opt == '-l':     lbound           = float(arg)
      elif opt == '-h':     hbound           = float(arg)
      elif opt == '-D':     demFile          = arg
      elif opt == '-C':     dispContour      = arg
      elif opt == '-V':     contour_step     = float(arg)
      elif opt == '-t':     minDate          = arg
      elif opt == '-T':     maxDate          = arg
      elif opt == '-r':     radius           = abs(int(arg))
      elif opt == '-x':     xsub = [int(i) for i in arg.split(':')];   xsub.sort();  # dispVelFig='no'
      elif opt == '-y':     ysub = [int(i) for i in arg.split(':')];   ysub.sort();  # dispVelFig='no'
      elif opt == '-X':     ref_xsub = [int(i) for i in arg.split(':')];   ref_xsub.sort();
      elif opt == '-Y':     ref_ysub = [int(i) for i in arg.split(':')];   ref_ysub.sort();  # dispVelFig='no'

      elif opt in ['-E','--exclude'] : datesNot2show   = arg.split(',')
      elif opt in ['--rect-color']   : rectColor       = arg
      elif opt in ['--ref-date']     : ref_date        = ptime.yyyymmdd(arg)
      elif opt in ['-u','--unit']    : unit            = arg.lower()
      elif opt == '--save'           : saveFig         = 'yes'
      elif opt == '--nodisplay'      : dispFig         = 'no';   saveFig='yes'

  ##############################################################
  ## Read time series file info
  if not os.path.isfile(timeSeriesFile):       Usage();sys.exit(1)
  h5timeseries = h5py.File(timeSeriesFile)
  k = h5timeseries.keys();       # read h5 file and its group type
  if not 'timeseries' in k:  print 'ERROR: Input file is '+k[0]+'.\n\tOnly timeseries is supported.\n'; sys.exit(1)
 
  atr = readfile.read_attributes(timeSeriesFile)
  dateList1 = h5timeseries['timeseries'].keys()
  dateList1 = sorted(dateList1)
  dates1,datevector1 = ptime.date_list2vector(dateList1)
  print '\n************ Time Series Display - Point *************'

  ##############################################################
  global dates, dateList, datevector_all

  print '*******************'
  print 'All dates existed:'
  print dateList1
  print '*******************'

  ## Check exclude date input
  try:
     datesNot2show
     print 'dates not to show: '+str(datesNot2show)
  except:  datesNot2show=[]

  ## Check Min / Max Date
  try:
    minDate
    minDateyy=ptime.yyyymmdd2years(minDate)
    print 'minimum date: '+minDate
    for date in dateList1:
       yy=ptime.yyyymmdd2years(date)
       if yy < minDateyy:
           datesNot2show.append(date)
  except:  pass
  try:
    maxDate
    maxDateyy=ptime.yyyymmdd2years(maxDate)
    print 'maximum date: '+maxDate
    for date in dateList1:
       yy=ptime.yyyymmdd2years(date)
       if yy > maxDateyy:
           datesNot2show.append(date)
  except:  pass

  ## Finalize Date List
  try:
     dateList=[]
     for date in dateList1:
        if date not in datesNot2show:
           dateList.append(date)
     print '--------------------------------------------'
     print 'dates used to show time series displacements:'
     print dateList
     print '--------------------------------------------'
  except:
     dateList=dateList1
     print 'using all dates to show time series displacement'

  ## Read Date Info (x axis for time series display)
  dates,datevector = ptime.date_list2vector(dateList)
  datevector_all = list(datevector)

  ## Check reference date input
  try:
      ref_date
      if not ref_date in dateList:
          print 'Reference date - '+ref_date+' - is not included in date list to show.'
          sys.exit(1)
      else: print 'reference date: '+ref_date
  except: pass

  ##############################################################
  ##### Plot Fig 1 - Velocity / last epoch of time series / DEM
  fig = plt.figure(1)
  ax=fig.add_subplot(111)

  try:
     velocityFile
     try:              #if input velocityFile = 'velocity.h5'
        h5file=h5py.File(velocityFile,'r')
        k=h5file.keys()
        dset= h5file[k[0]].get(k[0])
        ax.set_title(velocityFile)
        print 'display: ' + k[0]
     except:           #if input velocityFile = '20100217'
        epoch_number=dateList1.index(velocityFile)
        dset=h5timeseries['timeseries'].get(dateList1[epoch_number])
        ax.set_title('epoch: '+dateList1[epoch_number])
        print 'display epoch: '+dateList1[epoch_number]
  except:
     dset = h5timeseries['timeseries'].get(h5timeseries['timeseries'].keys()[-1])
     ax.set_title('epoch: '+dateList1[-1])
     print 'display last epoch'

  ## Reference Point
  if showRef == 'yes':
      try: ax.plot(int(atr['ref_x']),int(atr['ref_y']),'ks',ms=6)
      except: pass

  ## Flip
  orb_dir = orbit_direction(atr)
  print orb_dir+' orbit'
  ## flip by default if in radar coord
  try:
      atr['X_FIRST']
      geocoord = 'yes'
  except:
      geocoord = 'no'

  try: flip_lr
  except:
      if orb_dir == 'descending' and geocoord == 'no': flip_lr = 'yes'
      else:                                            flip_lr = 'no'
  try: flip_ud
  except:
      if orb_dir == 'ascending'  and geocoord == 'no': flip_ud = 'yes'
      else:                                            flip_ud = 'no'
  if flip_lr == 'yes':  print 'flip left and right'
  if flip_ud == 'yes':  print 'flip up   and down'


  ## Status bar
  def format_coord(x,y):
      col = int(x+0.5)
      row = int(y+0.5)
      if col>=0 and col<=dset.shape[1] and row >=0 and row<=dset.shape[0]:
         z = dset[row,col]
         return 'x=%.4f,  y=%.4f,  value=%.4f'%(x,y,z)
      else:
         return 'x=%.4f,  y=%.4f'%(x,y)
  ax.format_coord = format_coord

  ## DEM 
  try:
     demFile
     if   os.path.basename(demFile).split('.')[1]=='hgt':  amp,dem,demRsc = readfile.read_float32(demFile)
     elif os.path.basename(demFile).split('.')[1]=='dem':  dem,demRsc = readfile.read_dem(demFile)

     if dispContour in ('no','No','n','N','NO','yes','Yes','y','Y','YES'):
        print 'show DEM as basemap'
        cmap_dem=plt.get_cmap('gray')
        import pysar._pysar_utilities as ut
        plt.imshow(ut.hillshade(dem,50.0),cmap=cmap_dem)
     if dispContour in ('only','Only','o','O','ONLY','yes','Yes','y','Y','YES'):
        print 'show contour'
        if smoothContour in ('yes','Yes','y','Y','YES'):
           import scipy.ndimage as ndimage
           dem=ndimage.gaussian_filter(dem,sigma=10.0,order=0)
        contour_sequence=np.arange(-6000,9000,contour_step)
        plt.contour(dem,contour_sequence,origin='lower',colors='black',alpha=0.5)
  except: print 'No DEM file' 

  try:     img=ax.imshow(dset,vmin=vmin,vmax=vmax)
  except:  img=ax.imshow(dset)
  plt.colorbar(img)

  ## Flip
  if flip_lr == 'yes':  fig.gca().invert_xaxis()
  if flip_ud == 'yes':  fig.gca().invert_yaxis()


  ########################################## 
  ##### Plot Fig 2 - Time series plot
  #fig2 = plt.figure(num=2,figsize=(12,6))
  fig2 = plt.figure(2,figsize=(12,6))
  ax2  = fig2.add_subplot(111) 

  try:
     timeSeriesFile_2
     h5timeseries_2=h5py.File(timeSeriesFile_2)
     dateList_2 = h5timeseries_2['timeseries'].keys()
     dateList_2 = sorted(dateList_2)
     dates_2,datevector_2 = ptime.date_list2vector(dateList_2)
     datevector_all += list(set(datevector_2) - set(datevector_all))
     datevector_all = sorted(datevector_all)
  except:  pass


  ################################  Plot Code Package <start> #################################
  def plot_ts(ax,ax2,fig2,xsub,ysub,h5timeseries):
      ax2.cla()
      print '\n-------------------------------------------------------------------------------'
      disp_min = 0
      disp_max = 0

      ############################# Plot Time Series ##############################
      global ref_xsub, ref_ysub
      ##### 1.1 Plot Reference time series
      try:
          ref_xsub
          ref_ysub
          ref_xsub,ref_ysub = check_yx(ref_xsub,ref_ysub,radius,ax)
          print 'ref_x='+str(ref_xsub[0])+':'+str(ref_xsub[1]-1)
          print 'ref_y='+str(ref_ysub[0])+':'+str(ref_ysub[1]-1)
          print 'Reference Point - Time Series:'

          dis1, dis1_mean, dis1_std, dis1_vel = read_dis(ref_xsub,ref_ysub,dateList1,h5timeseries,unit)
          (_, caps, _)=ax2.errorbar(dates1,dis1_mean,yerr=dis1_std,fmt='-ks',\
                                    ms=markerSize2, lw=0, alpha=1,mfc=markerColor3,mew=edgeWidth,\
                                    elinewidth=edgeWidth,ecolor='black',capsize=markerSize*0.5)
          for cap in caps:  cap.set_markeredgewidth(edgeWidth)
          disp_min,disp_max = update_lim(disp_min,disp_max,dis1_mean,dis1_std)
          print '-----------------------------'
      except: pass

      ##### 1.2.0 Read y/x
      xsub,ysub = check_yx(xsub,ysub,radius,ax)
      print 'x='+str(xsub[0])+':'+str(xsub[1]-1)
      print 'y='+str(ysub[0])+':'+str(ysub[1]-1)

      ##### 1.2.1 Plot 2nd time series
      try:
          timeSeriesFile_2
          print '-----------------------------'
          print '2nd Time Series:'
          dis2, dis2_mean, dis2_std, dis2_vel = read_dis(xsub,ysub,dateList_2,h5timeseries_2,unit)
          (_, caps, _)=ax2.errorbar(dates_2,dis2_mean,yerr=dis2_std,fmt='-ko',\
                                    ms=markerSize2, lw=0, alpha=1, mfc=markerColor2,\
                                    elinewidth=edgeWidth,ecolor='black',capsize=markerSize*0.5)
          for cap in caps:  cap.set_markeredgewidth(edgeWidth)
          disp_min,disp_max = update_lim(disp_min,disp_max,dis2_mean,dis2_std)
      except: pass

      ##### 1.2.2 Plot 1st time series
      print '-----------------------------'
      print 'Time Series:'
      dis, dis_mean, dis_std, dis_vel = read_dis(xsub,ysub,dateList,h5timeseries,unit)
      (_, caps, _)=ax2.errorbar(dates,dis_mean,yerr=dis_std,fmt='-ko',\
                                ms=markerSize, lw=lineWidth, alpha=1, mfc=markerColor,\
                                elinewidth=edgeWidth,ecolor='black',capsize=markerSize*0.5)
      for cap in caps:  cap.set_markeredgewidth(edgeWidth)
      disp_min,disp_max = update_lim(disp_min,disp_max,dis_mean,dis_std)

      ####################### Figure Format #######################
      ## x axis format
      ax2 = adjust_xaxis_date(ax2,datevector_all)

      ## y axis format
      ax2.set_ylabel('Displacement ['+unit+']',fontsize=fontSize)
      try:
          lbound
          hbound
          ax2.set_ylim(lbound,hbound)
      except:
          disp_buf = 0.2*(disp_max - disp_min)
          ax2.set_ylim(disp_min-disp_buf,disp_max+disp_buf)
      for tick in ax2.yaxis.get_major_ticks():  tick.label.set_fontsize(fontSize)

      ## title
      ax2.set_title('x='+str(xsub[0])+':'+str(xsub[1]-1)+', y='+str(ysub[0])+':'+str(ysub[1]-1))

      ################## Save and Output #####################
      if saveFig == 'yes':
          Delay={}
          Delay['displacement'] = dis
          Delay['unit']         = unit
          Delay['time']         = datevector
          Delay['velocity']     = dis_vel[0]
          Delay['velocity_unit']= unit+'/yr'
          Delay['velocity_std'] = dis_vel[4]
          figBase = 'x'+str(xsub[0])+'_'+str(xsub[1]-1)+'y'+str(ysub[0])+'_'+str(ysub[1]-1)
          sio.savemat( figBase+'_ts.mat', {'displacement': Delay});                               print 'saved '+figBase+'_ts.mat'
          fig2.savefig(figBase+'_ts.pdf',bbox_inches='tight',transparent=True,dpi=fig_dpi);       print 'saved '+figBase+'_ts.pdf'
          if dispFig == 'no':
              fig.savefig(figBase+'_vel.png',bbox_inches='tight',transparent=True,dpi=fig_dpi);   print 'saved '+figBase+'_vel.png'
  ################################  Plot Code Package <end> #################################



  ########### 1. Plot Time Series with x/y ##########
  try:
      xsub
      ysub
      plot_ts(ax,ax2,fig2,xsub,ysub,h5timeseries)
  except:  print 'No x/y input' ; pass


  ########### 2. Plot Time Series with Click ##########
  ## similar to 1. Plot Time Series with x/y

  def onclick(event):
      ax2.cla()
      xsub = [int(event.xdata)]
      ysub = [int(event.ydata)]
      plot_ts(ax,ax2,fig2,xsub,ysub,h5timeseries)

      if dispFig == 'yes':  plt.show()

  try: cid = fig.canvas.mpl_connect('button_press_event', onclick)
  except: pass

  if dispFig == 'yes':  plt.show()


####################################################################################
if __name__ == '__main__':
  main(sys.argv[1:])




