# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import pandas as pd
import plotly.graph_objs as go
import plotly.plotly as py
from plotly import tools
import matplotlib.pyplot as plt
import h5py
import numpy as np
import os, base64
from io import BytesIO

import torch # Unsure of Overhead
from torch.autograd import Variable
import torch.nn.functional as F

import gym
from visualize_atari import *

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

server = app.server

log_data = pd.read_csv("baby-a3c/breakout-v4/log-model7-02-17-20-41.txt")
log_data.columns = log_data.columns.str.replace(" ", "")
log_data['frames'] = log_data['frames']/500e3

replays = h5py.File('static/model_rollouts_5.h5','r')
logits = replays['models_model7-02-17-20-41/model.30.tar/history/0/logits'].value
ins = replays['models_model7-02-17-20-41/model.30.tar/history/0/ins'].value
softmax_logits = F.softmax(torch.from_numpy(logits), dim=1).numpy()
traces = []
actions = ['NOOP', 'FIRE', 'RIGHT', 'LEFT']
for a in range(softmax_logits.shape[1]):
    trace = dict(
        x = list(range(softmax_logits.shape[0])),
        y = softmax_logits[:, a],
        hoverinfo = 'x+y',
        mode = 'lines',
        line = dict(width=0.5),
        stackgroup = 'one',
        name = actions[a]
    )
    traces.append(trace) 

    
app.layout = html.Div(children=[
    html.H1(children='Interactive Atari RL'),
    html.Div([
        dcc.Graph(
            figure = go.Figure(
                data = traces
            )
        )
    ]),
    html.Div([
        html.Div([
            html.Div(id='frame-val'),
            dcc.Slider(id='frame-slider',
                   min = 0,
                   max = 2500,
                   value = 0,
                   marks = {i: str(i) for i in range(0, 2500, 100)},
                   step = None
               
                  )
        ], style = {'padding-bottom':'50px', 'padding-left':'10px'}),
        html.Div([
            html.Div(id='snapshot-val'),
            dcc.Slider(id='snapshot-slider',
                   min = 1,
                   max = 100,
                   value = 50,
                   marks = {i: str(i) for i in range(0, 100, 5)},
                   #step = None
               
                  )
        ])
    ], style={'padding-bottom':'20px'}),
    html.Div([
        html.Div(html.Img(id = 'screen-ins',width='320'), style = {'display':'inline-block'}),
        html.Div(dcc.Graph(id = 'regions_subplots'
                           ), style={'display':'inline-block'})
    ]),
    html.Div(children=[dcc.Graph(
                           id='mean-epr_over_eps',
                           figure={
                               'data': [
                                   #py.iplot(log_data['episodes'], log_data['mean-epr'])
                                   go.Scatter(x=log_data['frames'],
                                              y=log_data['mean-epr'])
                               ],
                               'layout': {
                                   'xaxis': {'title': '500k Frames'},
                                   'yaxis': {'title': 'Mean reward'},
                                   'title': 'mean episode rewards over episodes'
                               }
                           },
                           style={'float':'left','width':'50%'}
                       ),
                       dcc.Graph(
                           id='loss_over_eps',
                           figure={
                               'data': [
                                   #py.iplot(log_data['episodes'], log_data['mean-epr'])
                                   go.Scatter(x=log_data['frames'],
                                              y=log_data['run-loss'])

                               ],
                               'layout': {
                                   'xaxis': {'title': '500k Frames'},
                                   'yaxis': {'title': 'Loss'},
                                   'title': 'loss over episodes'
                               }
                           },
                           style={'float':'right','width':'50%'}
                       )
                       ]
           
             )
           
])

@app.callback(
    Output(component_id='frame-val', component_property='children'),
    [Input(component_id='frame-slider', component_property='value')]
)
def update_frame_slider(input_value):
    return 'Frame number of episode: {}'.format(input_value)

@app.callback(
    Output(component_id='snapshot-val', component_property='children'),
    [Input(component_id='snapshot-slider', component_property='value')]
)
def update_snapshot_slider(input_value):
    return 'Model iteration (500k frame increments): {}'.format(input_value)

@app.callback(
    Output(component_id='screen-ins', component_property='src'),
    [Input(component_id='frame-slider', component_property='value'),
     Input('snapshot-slider', 'value')]
)
def update_frame_in_slider(frame, snapshot):
    # fetch frame based on snapshot and frame
    img = ins.copy()
    if frame > len(img):
        img = np.zeros((210,160,3))
    else: img = img[frame]
    buffer = BytesIO()
    plt.imsave(buffer, img)
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return 'data:image/png;base64,{}'.format(img_str)

@app.callback(
    Output(component_id='regions_subplots', component_property='figure'),
    [Input(component_id='frame-slider', component_property='value')]
)
def update_regions_plots(frame):
    img = ins.copy()
    if frame > len(img):
        img = np.zeros((210,160,3))
    else: img = img[frame]
    
    ymid, xmid = 110, 80
    
    it = 30

    history = replays['models_model7-02-17-20-41/model.30.tar/history/0']
    actor_frames = history['actor_sal'].value
    critic_frames = history['critic_sal'].value
    
    actor_tot = actor_frames.sum((1,2))
    critic_tot = critic_frames.sum((1,2))
   
    targets = [(actor_frames[:, :40, :40], critic_frames[:, :40, :40]),
               (actor_frames[:, :40, 40:], critic_frames[:, :40, 40:]),
               (actor_frames[:, 40:, :40], critic_frames[:, 40:, :40]),
               (actor_frames[:, 40:, 40:], critic_frames[:, 40:, 40:])]
    # intensity defined by sum of values in frame region divided by sum of total values of full frame
    
    trace_labels = ['TopLeft', 'TopRight', 'BotLeft', 'BotRight']
    
    a_traces = []
    for i in range(4):
        print((targets[i][0]).shape)
        trace = dict(
            x = list(range(0, actor_frames.shape[0] * 100, 100)),
            y = (targets[i][0]).sum((1,2)) / actor_tot,
            hoverinfo = 'x+y',
            line = dict(
                color = ('rgb(24, 12, 205)'),
                width = 3)
        )

        a_traces.append(trace)
        
    c_traces = []
    for i in range(4):
        print((targets[i][0]).shape)
        trace = dict(
            x = list(range(0, actor_frames.shape[0] * 100, 100)),
            y = (targets[i][1]).sum((1,2)) / critic_tot,
            hoverinfo = 'x+y',
            line = dict(
                color = ('rgb(205, 12, 24)'),
                width = 3)
        )

        c_traces.append(trace)
    fig = tools.make_subplots(rows=2, cols=2, subplot_titles=('Top left', 'Top Right',
                                                          'Bottom left', 'Bottom Right'))
    
    for series in [a_traces, c_traces]:
        fig.append_trace(series[0], 1, 1)
        fig.append_trace(series[1], 1, 2)
        fig.append_trace(series[2], 2, 1)
        fig.append_trace(series[3], 2, 2)
    
    fig['layout'].update(title='Saliency intensity by quarter region', showlegend=False)
    fig['layout']['xaxis3'].update(title='Frame')
    fig['layout']['xaxis4'].update(title='Frame')
    fig['layout']['yaxis1'].update(title='Intensity', range=[0,1])
    fig['layout']['yaxis3'].update(title='Intensity', range=[0,1])
    fig['layout']['yaxis2'].update(range=[0,1])
    fig['layout']['yaxis4'].update( range=[0,1])
    fig['layout']['xaxis1'].update(anchor='x3')
    fig['layout']['xaxis2'].update(anchor='x4')

    return fig


# def update_frame_in_slider(frame, snapshot):
#     # fetch frame based on snapshot and frame
#     images = 'static/images'
#     avail = os.listdir(images)
#     if str(snapshot) not in avail:
#         return os.path.join(images, 'dead.png') # some default val, return something else later
    
#     snapshot_dir = os.path.join(images, str(snapshot))
#     if str(frame) not in [name.split('.')[0] for name in os.listdir(snapshot_dir)]:
#         return os.path.join(images, 'dead.png') # if frame not there
#     #print(os.path.join(snapshot_dir, str(frame)+'.png'))
#     return os.path.join(snapshot_dir, str(frame)+'.png')
    

if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0')
