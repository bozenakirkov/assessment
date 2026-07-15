from state_machine import get_manual_transition


class WorkflowService:


    def transition(self, current_state, action):

        new_state = get_manual_transition(
            current_state,
            action
        )

        return new_state