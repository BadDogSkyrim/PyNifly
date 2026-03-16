$configPath = "C:\Steam\steamapps\common\Skyrim Special Edition\Data\SKSE\Plugins\hdtSkinnedMeshConfigs"
$files = Get-ChildItem "$configPath\HDTTail*.xml"

foreach ($file in $files) {
    Write-Host "`n=== Processing $($file.Name) ==="
    
    $lines = Get-Content $file.FullName -Encoding UTF8
    
    # Find VirtualGround block
    $vgStart = -1
    $vgEnd = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '<per-triangle-shape name="VirtualGround">') {
            $vgStart = $i
        }
        if ($vgStart -ge 0 -and $lines[$i] -match '</per-triangle-shape>') {
            $vgEnd = $i
            break
        }
    }
    
    if ($vgStart -lt 0) {
        Write-Host "  No VirtualGround found, skipping"
        continue
    }
    
    Write-Host "  VirtualGround currently at line $($vgStart + 1)"
    
    # If already at top (line 3-5), skip
    if ($vgStart -le 5) {
        Write-Host "  Already at top, checking for penetration fix..."
        
        # Check if needs penetration -> prenetration fix
        $needsFix = $false
        for ($i = $vgStart; $i -le $vgEnd; $i++) {
            if ($lines[$i] -match '<penetration>') {
                $needsFix = $true
                break
            }
        }
        
        if ($needsFix) {
            Write-Host "  Fixing penetration -> prenetration"
            $lines[$i] = $lines[$i] -replace '<penetration>', '<prenetration>'
            $lines[$i] = $lines[$i] -replace '</penetration>', '</prenetration>'
            $lines | Set-Content $file.FullName -Encoding UTF8
            Write-Host "  Fixed!"
        } else {
            Write-Host "  No changes needed"
        }
        continue
    }
    
    # Backup
    Copy-Item $file.FullName "$($file.FullName).backup"
    Write-Host "  Created backup: $($file.Name).backup"
    
    # Extract VirtualGround block
    $vgBlock = $lines[$vgStart..$vgEnd]
    
    # Fix penetration -> prenetration in the block
    for ($i = 0; $i -lt $vgBlock.Count; $i++) {
        $vgBlock[$i] = $vgBlock[$i] -replace '<penetration>', '<prenetration>'
        $vgBlock[$i] = $vgBlock[$i] -replace '</penetration>', '</prenetration>'
    }
    
    # Remove old VirtualGround block
    $newLines = @()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($i -lt $vgStart -or $i -gt $vgEnd) {
            $newLines += $lines[$i]
        }
    }
    
    # Find insertion point (after <system> tag and before first bone)
    $insertAt = -1
    for ($i = 0; $i -lt $newLines.Count; $i++) {
        if ($newLines[$i] -match '<system ') {
            $insertAt = $i + 1
            # Skip blank lines and comments
            while ($insertAt -lt $newLines.Count -and ($newLines[$insertAt] -match '^\s*$' -or $newLines[$insertAt] -match '^\s*<!--')) {
                $insertAt++
            }
            break
        }
    }
    
    # Insert VirtualGround at top
    $finalLines = @()
    for ($i = 0; $i -lt $newLines.Count; $i++) {
        if ($i -eq $insertAt) {
            $finalLines += ""
            $finalLines += $vgBlock
            $finalLines += ""
        }
        $finalLines += $newLines[$i]
    }
    
    # Save
    $finalLines | Set-Content $file.FullName -Encoding UTF8
    Write-Host "  Moved VirtualGround to line $($insertAt + 2) and fixed penetration"
    Write-Host "  Done!"
}

Write-Host "`n=== All tail configs processed ==="
