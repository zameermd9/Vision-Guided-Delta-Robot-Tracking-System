PROGRAM _CYCLIC

	TargetValid := HR_TargetValid1 = 1;

	IF TargetValid THEN

		VisionX := UINT_TO_DINT(HR_X_Target1) - X_OFFSET;
		VisionY := UINT_TO_DINT(HR_Y_Target1) - Y_OFFSET;

		IF HR_SeqCounter1 <> LastSeq THEN
			NewVisionData := TRUE;
			LastSeq := HR_SeqCounter1;
		ELSE
			NewVisionData := FALSE;
		END_IF

	ELSE
		NewVisionData := FALSE;
	END_IF

	TrackingActive := StartTrackingCmd1 AND TargetValid;

END_PROGRAM
