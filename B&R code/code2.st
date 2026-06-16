VAR CONSTANT
Pos1     : McPointType := (Pos := (X := 0, Y := 0, Z := -432));
SafeZPos : McPointType := (Pos := (X := 0, Y := 0, Z := -320));
Pos2Base : McPointType := (Pos := (X := 0, Y := 0, Z := -320));
	END_VAR

	VAR
FollowPos : McPointType;
X_cmd     : DINT;
Y_cmd     : DINT;
i         : UDINT;
	END_VAR

	VAR {AT 'tracking'}
StartTrackingCmd1 : BOOL;
VisionX           : DINT;
VisionY           : DINT;
	END_VAR

	PROGRAM _MAIN

	Feedrate(5000);

	MoveL(Pos1);
	WaitEndMove();

	MoveL(SafeZPos);
	WaitEndMove();

	StartTrackingCmd1 := TRUE;

	FOR i := 1 TO 200 DO

		X_cmd := VisionX;
		Y_cmd := VisionY;

		FollowPos := Pos2Base;

		// X safety limit
		IF X_cmd > 45 THEN
			FollowPos.Pos.X := 45;
		ELSIF X_cmd < -45 THEN
			FollowPos.Pos.X := -45;
		ELSE
			FollowPos.Pos.X := X_cmd;
		END_IF

		// Y safety limit
		IF Y_cmd > 35 THEN
			FollowPos.Pos.Y := 35;
		ELSIF Y_cmd < -35 THEN
			FollowPos.Pos.Y := -35;
		ELSE
			FollowPos.Pos.Y := Y_cmd;
		END_IF

		FollowPos.Pos.Z := -320;

		MoveL(FollowPos);
		WaitEndMove();

		WaitTime(0.1);

	END_FOR

	StartTrackingCmd1 := FALSE;

	MoveL(SafeZPos);
	WaitEndMove();

	MoveL(Pos1);
	WaitEndMove();

	END_PROGRAM
