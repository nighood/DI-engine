from turtle import Terminator
import gym
from ditk import logging
from ding.model import VAC
from ding.policy import PPOPolicy
from ding.envs import DingEnvWrapper, BaseEnvManagerV2
from ding.data import DequeBuffer
from ding.config import compile_config
from ding.framework import task
from ding.framework.context import OnlineRLContext
from ding.framework.middleware import multistep_trainer, StepCollector, interaction_evaluator, CkptSaver, gae_estimator,termination_checker
from ding.utils import set_pkg_seed
from dizoo.rocket.envs.rocket_env import RocketEnv
from dizoo.rocket.config.rocket_ppo_config import main_config, create_config
import numpy as np
from tensorboardX import SummaryWriter
import os

def main():
    logging.getLogger().setLevel(logging.INFO)
    main_config.exp_name = 'rocket_ppo_nseed'
    cfg = compile_config(main_config, create_cfg=create_config, auto=True)
    num_seed = 1
    for seed_i in range(num_seed):
        tb_logger = SummaryWriter(os.path.join('./{}/log/'.format(cfg.exp_name), 'seed'+str(seed_i)))
        with task.start(async_mode=False, ctx=OnlineRLContext()):
            collector_env = BaseEnvManagerV2(
                env_fn=[lambda: RocketEnv(cfg.env) for _ in range(cfg.env.collector_env_num)],
                cfg=cfg.env.manager
            )
            evaluator_env = BaseEnvManagerV2(
                env_fn=[lambda: RocketEnv(cfg.env) for _ in range(cfg.env.evaluator_env_num)],
                cfg=cfg.env.manager
            )

            # evaluator_env.enable_save_replay()

            set_pkg_seed(seed_i, use_cuda=cfg.policy.cuda)

            model = VAC(**cfg.policy.model)
            policy = PPOPolicy(cfg.policy, model=model)

            def _add_scalar(ctx):
                if ctx.eval_value != -np.inf:
                    tb_logger.add_scalar('evaluator_step/reward', ctx.eval_value, global_step= ctx.env_step)

            task.use(interaction_evaluator(cfg, policy.eval_mode, evaluator_env))
            task.use(StepCollector(cfg, policy.collect_mode, collector_env))
            task.use(gae_estimator(cfg, policy.collect_mode))
            task.use(multistep_trainer(cfg, policy.learn_mode))
            task.use(CkptSaver(cfg, policy, train_freq=100))
            task.use(_add_scalar)
            # task.use(termination_checker(max_env_step=int(10e8)))
            task.run()


if __name__ == "__main__":
    main()
