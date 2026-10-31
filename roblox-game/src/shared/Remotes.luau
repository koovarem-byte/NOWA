--!strict
-- Связь сервер <-> клиент.
-- Сервер создаёт папку Remotes и папку GameState, клиент их ждёт.
--
-- Remotes:
--   Kick    (клиент -> сервер)  сила удара 0..1
--   Message (сервер -> клиент)  текст на экране
--   Scare   (сервер -> клиент)  скример / тряска / звук
--
-- GameState — папка с атрибутами (их видят все клиенты):
--   Phase ("Lobby" | "Football" | "Horror" | "End"), TimeLeft, ScoreHouse, ScoreFence,
--   Anger, DoorHP, DoorClosed

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local REMOTE_NAMES = { "Kick", "Message", "Scare" }

local Remotes = {}

local remotesFolder: Instance
local stateFolder: Instance

if RunService:IsServer() then
	local existing = ReplicatedStorage:FindFirstChild("Remotes")
	if existing then
		remotesFolder = existing
	else
		local f = Instance.new("Folder")
		f.Name = "Remotes"
		for _, name in REMOTE_NAMES do
			local r = Instance.new("RemoteEvent")
			r.Name = name
			r.Parent = f
		end
		f.Parent = ReplicatedStorage
		remotesFolder = f
	end

	local existingState = ReplicatedStorage:FindFirstChild("GameState")
	if existingState then
		stateFolder = existingState
	else
		local s = Instance.new("Folder")
		s.Name = "GameState"
		s.Parent = ReplicatedStorage
		stateFolder = s
	end
else
	remotesFolder = ReplicatedStorage:WaitForChild("Remotes")
	stateFolder = ReplicatedStorage:WaitForChild("GameState")
end

function Remotes.get(name: string): RemoteEvent
	return remotesFolder:WaitForChild(name) :: RemoteEvent
end

function Remotes.state(): Instance
	return stateFolder
end

return Remotes
