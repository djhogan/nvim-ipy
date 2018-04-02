import sys
import time
import neovim
from queue import Empty
from jupyter_core.application import JupyterApp
from jupyter_client.consoleapp import JupyterConsoleApp
from jupyter_client.threaded import ThreadedKernelClient

@neovim.plugin
class Main:
    def __init__(self, vim):
        self.vim = vim

    @neovim.function('IPyStart', sync=False)
    def launch_instance(self, args):
        self.ipy = ZMQVimIPythonApp()
        self.ipy.initialize(self)
        self.ipy.start()

    @neovim.function('IPyRun')
    def run_cell(self, args):
        line = self.vim.eval('getline(".")')
        self.ipy.run_cell(line)

    def write(self, text):
        self.vim.command('new')
        self.vim.current.buffer.append(text.split('\n'))

class ZMQVimIPythonApp(JupyterApp, JupyterConsoleApp):
    name = 'jupyter-vim'
    version = '1.0'
    # kernel_client_class = ThreadedKernelClient

    def initialize(self, out):
        super(ZMQVimIPythonApp, self).initialize(None)
        JupyterConsoleApp.initialize(self) # XXX why do we call it again?
        self.out = out

    def start(self):
        super(ZMQVimIPythonApp, self).start()
        tic = time.time()
        # XXX self.kernel_client.hb_channel.unpause()
        msg_id = self.kernel_client.kernel_info()
        while True:
            try:
                reply = self.kernel_client.get_shell_msg(timeout=1.0)
            except Empty:
                if (time.time() - tic) > 5.0:
                    raise RuntimeError("Kernel didn't respond to kernel_info request.")
            else:
                if reply['parent_header'].get('msg_id') == msg_id:
                    self.kernel_info = reply['content']
                    return

    def run_cell(self, cell):
        # TODO flush stale replies
        msg_id = self.kernel_client.execute(cell)
        self._execution_state = 'busy'

        # function handle stuff while executing
        while self._execution_state != 'idle' and self.kernel_client.is_alive():
            time.sleep(0.1)
            self.handle_iopub()
            # TODO handle input request
        while self.kernel_client.is_alive():
            try:
                self.handle_execute_reply(msg_id)
            except Empty:
                pass
            else:
                break
        # TODO handle input request

    def handle_input_request(self, msg_id, timeout=0.1):
        raise NotImplementedError()
        req = self.kernel_client.stdin_channel.get_msg(timeout=timeout)
        self.handle_iopub(msg_id)
        if msg_id == req['parent_header']['msg_id']:
            # TODO handle SIGINT
            content = req['content']

    def handle_execute_reply(self, msg_id, timeout=0.1):
        msg = self.kernel_client.shell_channel.get_msg(block=False, timeout=timeout)
        if msg['parent_header'].get('msg_id', None) == msg_id:
            self.handle_iopub()  # XXX why is this here?
            content = msg['content']
            status = content['status']
            if status == 'aborted':
                raise RuntimeError('Aborted while waiting for shell channel reply.')
            elif status == 'ok':
                for item in content.get('payload', []):
                    source = item['source']
                    raise NotImplementedError('Execute reply payloads.')
            elif status == 'error':
                raise RuntimeError('Waiting for shell channel reply, received error reply.')
        else:
            raise RuntimeError(f'Waiting for shell channel reply, but received unrelated message: {msg}.')

    def handle_iopub(self, msg_id=''):
        while self.kernel_client.iopub_channel.msg_ready():
            sub_msg = self.kernel_client.iopub_channel.get_msg()
            msg_type = sub_msg['header']['msg_type']
            parent = sub_msg['parent_header']

            if True: # check if from here
                if msg_type == 'status':
                    self._execution_state = sub_msg['content']['execution_state']
                elif msg_type == 'stream':
                    self.out.write(sub_msg['content']['text'])
                elif msg_type == 'display_data':
                    self.out.write(sub_msg['content']['data']['text/plain'])
                    # TODO handle other data types.
                elif msg_type == 'data_pub':
                    pass # TODO raw data
                elif msg_type == 'execute_result':
                    self.out.write(sub_msg['content']['data']['text/plain'])
                    # TODO
                elif msg_type == 'execute_input':
                    self.out.write(sub_msg['content']['code'] + '\n')
                elif msg_type == 'clear_output':
                    pass # TODO used for clearing output. Useful for animations.
                elif msg_type == 'error':
                    self.out.write(sub_msg)

    def handle_stdin(self, msg_id=''):
        raise NotImplementedError()

    def handle_control(self, msg_id=''):
        raise NotImplementedError()

if __name__ == '__main__':
    ZMQVimIPythonApp.launch_instance()
