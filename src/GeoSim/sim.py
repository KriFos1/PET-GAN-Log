import numpy as np
import os
from NeuralSim.vector_to_log import FullModel
import torch
from copy import deepcopy

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class GeoSim:
    def __init__(self,input_dict=None):

        # some mandatory stuff
        assert 'file_name' in input_dict, 'file_name is missing, specify the path to the GAN weights!'
        assert 'full_em_model_file_name' in input_dict, 'full_em_model_file_name is missing, specify the path to the EM model weights!'
        assert 'scalers_folder' in input_dict, 'scalers_folder is missing, specify the path to the folder containing the scalers!'

        if 'vec_size' in input_dict:
            self.vec_size = input_dict['vec_size']
        else:
            self.vec_size = 60

        input_shape = (3,128) # These are fixed
        output_shape = (6,18)


        self.NNmodel = FullModel(latent_size=self.vec_size,
                    gan_save_file=input_dict['file_name'],
                    proxi_save_file=input_dict['full_em_model_file_name'],
                    proxi_scalers=input_dict['scalers_folder'],
                    proxi_input_shape=input_shape,
                    proxi_output_shape=output_shape,
                    gan_output_height=64,
                    num_img_channels=6,
                    gan_correct_orientation=True,
                    device=device
                    )

        self.names = [
            'real(xx)', 'img(xx)',
            'real(yy)', 'img(yy)',
            'real(zz)', 'img(zz)',
            'real(xz)', 'img(xz)',
            'real(zx)', 'img(zx)',
            'USDA', 'USDP',
            'UADA', 'UADP',
            'UHRA', 'UHRP',
            'UHAA', 'UHAP'
        ]

    def run_fwd_sim(self, state, member_i):

        state['member_i'] = member_i

        self.pred_data = self.call_sim(**state)

        return self.pred_data

    def run_Jacobian(self,**kwargs):
        my_latent_vec_np = kwargs['x']
        my_latent_tensor = torch.tensor(my_latent_vec_np.tolist(), dtype=torch.float32, requires_grad=True).unsqueeze(
            0).to(device)
        index_tensor_bw = torch.full((1, 2), fill_value=32, dtype=torch.long).to(device)
        jacobean = torch.autograd.functional.jacobian(lambda x: self.full_model.forward(x, index_vector=index_tensor_bw),
                                                      my_latent_tensor,
                                                      create_graph=False,
                                                      vectorize=True)
        return jacobean.cpu().detach().numpy()

    def setup_fwd_run(self,kwargs):

        self.__dict__.update(kwargs)  # parse kwargs input into class attributes
        self.pred_data = [deepcopy({}) for _ in range(max(self.l_prim)+1)]
        for ind in range(max(self.l_prim)+1):
            for key in self.all_data_types:
                self.pred_data[ind][key] = np.zeros((1, 1))

        # Initialize the index_vector for the call_sim method
        self.index_vector = torch.full((1, 1), fill_value=32, dtype=torch.long).to(device)

    def call_sim(self, **kwargs):
        my_latent_vec_np = kwargs['x']
        my_latent_tensor = torch.tensor(my_latent_vec_np, dtype=torch.float32).unsqueeze(0).to(
            device)  # Add batch dimension and move to device

        logs = self.NNmodel.forward(my_latent_tensor,self.index_vector,output_transien_results=False)

        logs_np = logs.cpu().detach().numpy()
#        cols, setups, log_types = logs_np.shape

        for prim_ind in range(max(self.l_prim)+1):
            # Loop over all keys in pred_data (all data types)
            for key in self.all_data_types:
                if self.pred_data[prim_ind][key] is not None:  # Obs. data at assim. step
                    extract_index = self.tool_configs.index(key)
                    self.pred_data[prim_ind][key] = logs_np[:,extract_index,:].flatten()

        return self.pred_data

if __name__ == "__main__":
    weights_folder = "https://gitlab.norceresearch.no/saly/image_to_log_weights/-/raw/master/em/{}.pth?ref_type=heads"
    scalers_folder = weights_folder
    full_em_model_file_name = "https://gitlab.norceresearch.no/saly/image_to_log_weights/-/raw/master/em/checkpoint_770.pth?ref_type=heads"
    file_name = "https://gitlab.norceresearch.no/saly/image_to_log_weights/-/raw/master/gan/netG_epoch_15000.pth"

    input_dict = {
        'file_name':file_name,
        'full_em_model_file_name':full_em_model_file_name,
        'scalers_folder':scalers_folder
         }

    sim = GeoSim(input_dict)

    sim.l_prim = [0]
    sim.all_data_types = ["('6kHz', '83ft')","('12kHz', '83ft')","('24kHz', '83ft')","('24kHz', '43ft')","('48kHz', '43ft')","('96kHz', '43ft')"]
    sim.tool_configs = sim.all_data_types

    sim.setup_fwd_run({'bah':10})

    latent_model = np.random.normal(size=60)

    pred = sim.run_fwd_sim({'x':latent_model},member_i=0)
    print(pred[0])
