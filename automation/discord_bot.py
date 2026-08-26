import os
import asyncio
import discord
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv
from automation.approval_gate import ApprovalManager
from automation.runtime_state import RuntimeStateManager
from automation.models import TaskState

load_dotenv()

class ApprovalView(View):
    def __init__(self, approval_id: str, task_id: str, project_id: str, action: str, approver_ids: list):
        super().__init__(timeout=None)
        self.approval_id = approval_id
        self.task_id = task_id
        self.project_id = project_id
        self.action_req = action
        self.approver_ids = approver_ids
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) not in self.approver_ids:
            await interaction.response.send_message("You are not authorized to approve or reject tasks.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="btn_approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_decision(interaction, True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red, custom_id="btn_reject")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_decision(interaction, False)
        
    async def _handle_decision(self, interaction: discord.Interaction, approved: bool):
        root_dir = os.environ.get("PROJECT_ROOT", os.getcwd())
        app_mgr = ApprovalManager(root_dir)
        
        # Check if approval exists and is pending
        app = app_mgr.get_approval(self.approval_id)
        if not app:
            await interaction.response.send_message("Approval request not found or invalid.", ephemeral=True)
            return
            
        if app.status != "PENDING":
            await interaction.response.send_message(f"This request was already decided: {app.status}", ephemeral=True)
            self.stop()
            return
            
        # Validation checks
        if app.task_id != self.task_id or app.action != self.action_req:
            await interaction.response.send_message("Approval context mismatch. Denied.", ephemeral=True)
            return
            
        # Execute decision
        success = app_mgr.decide(self.approval_id, approved, source=f"Discord User {interaction.user.id}")
        if success:
            action_str = "APPROVED" if approved else "REJECTED"
            await interaction.response.send_message(f"Task `{self.task_id}` action `{self.action_req}` was {action_str}.")
            
            # Disable buttons
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
            self.stop()
        else:
            await interaction.response.send_message("Failed to process decision. State might have changed.", ephemeral=True)

class DiscordApprovalBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        # We do not need message_content since we only respond to interactions
        # intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        print("Discord Approval Bot is ready and listening for interactions.")

    async def on_interaction(self, interaction: discord.Interaction):
        print("Interaction received:", interaction.type, interaction.data)
        if interaction.type != discord.InteractionType.component:
            return
            
        custom_id = interaction.data.get("custom_id", "")
        print("Custom ID:", custom_id)
        if not (custom_id.startswith("approve_") or custom_id.startswith("reject_")):
            return
            
        parts = custom_id.split("_", 2)
        if len(parts) < 3:
            return
            
        action_type = parts[0] # approve or reject
        task_id = parts[1]
        app_id = parts[2]
        
        approver_ids_str = os.environ.get("DISCORD_APPROVER_USER_IDS", "")
        approver_ids = [x.strip() for x in approver_ids_str.split(",") if x.strip()]
        print("Approver IDs:", approver_ids)
        
        if str(interaction.user.id) not in approver_ids:
            print("User unauthorized", interaction.user.id)
            await interaction.response.send_message("You are not authorized to approve or reject tasks.", ephemeral=True)
            return
            
        root_dir = os.environ.get("PROJECT_ROOT", os.getcwd())
        app_mgr = ApprovalManager(root_dir)
        
        app = app_mgr.get_approval(app_id)
        if not app:
            print("Approval not found")
            await interaction.response.send_message("Approval request not found or invalid.", ephemeral=True)
            return
            
        if app.status != "PENDING":
            print("Approval already decided:", app.status)
            await interaction.response.send_message(f"This request was already decided: {app.status}", ephemeral=True)
            return
            
        if app.task_id != task_id:
            print("Mismatch:", app.task_id, task_id)
            await interaction.response.send_message("Approval context mismatch. Denied.", ephemeral=True)
            return
            
        approved = (action_type == "approve")
        success = app_mgr.decide(app_id, approved, source=f"Discord User {interaction.user.id}")
        print("Decide success:", success)
        
        if success:
            action_str = "APPROVED" if approved else "REJECTED"
            try:
                msg = interaction.message
                if msg:
                    # Let's just edit content, avoid re-attaching raw components
                    await interaction.response.edit_message(content=msg.content + f"\n\n**Status:** {action_str} by <@{interaction.user.id}>", view=None)
                else:
                    await interaction.response.send_message(f"Task `{task_id}` was {action_str}.")
            except Exception as e:
                print(f"Error updating message: {e}")
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"Task `{task_id}` was {action_str}.")
        else:
            await interaction.response.send_message("Failed to process decision. State might have changed.", ephemeral=True)

def start_bot():
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("DISCORD_BOT_TOKEN not found. Bot will not start.")
        return
        
    bot = DiscordApprovalBot()
    bot.run(token)

if __name__ == "__main__":
    start_bot()
